import csv
import fcntl
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from src.schemas import Booking, valid_contact

class Leads:
    def __init__(self,path,inventory):
        self.path,self.inventory = path,inventory
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a+',newline='') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            f.seek(0)
            if not f.read(1): csv.DictWriter(f,fieldnames=list(Booking.model_fields)).writeheader()

    def rows(self):
        with self.path.open(newline='') as f:
            fcntl.flock(f,fcntl.LOCK_SH)
            return list(csv.DictReader(f))

    def qualify(self,user_id,name,contact,budget,notes):
        """Record an inquiry independently of booking eligibility or slot selection.

        Empty slot fields identify a qualified inquiry, never a reserved slot.
        """
        if not valid_contact(contact) or budget <= 0: return
        row=dict(user_id=user_id,user_name=name,contact=contact,car_id='',requested_day='',requested_hour_24='',budget_max=budget,notes=notes)
        with self.path.open('r+',newline='') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            rows=list(csv.DictReader(f))
            rows=[r for r in rows if not (r['user_id']==user_id and not r['requested_day'])]
            rows.append(row)
            f.seek(0)
            writer=csv.DictWriter(f,fieldnames=list(Booking.model_fields))
            writer.writeheader(); writer.writerows(rows); f.truncate(); f.flush()

    def book(self, booking):
        car = self.inventory.get(booking.car_id)
        if not car or car.get('dubizzle_managed') is not True:
            return {'ok':False,'reason':'Viewings require a confirmed dubizzle-managed listing.','alternatives':[]}
        now = datetime.now(ZoneInfo('Asia/Dubai'))
        today = now.date()
        try:
            day = date.fromisoformat(booking.requested_day)
        except ValueError:
            days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            if booking.requested_day.lower() not in days:
                return {'ok':False,'reason':'Use an ISO date or weekday.','alternatives':[]}
            day = today + timedelta(days=(days.index(booking.requested_day.lower())-today.weekday())%7)
        with self.path.open('r+',newline='') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            rows = list(csv.DictReader(f))
            taken = {(r['car_id'],r['requested_day'],int(r['requested_hour_24'])) for r in rows if r['requested_day'] and r['requested_hour_24'] != ''}
            def valid(d,h):
                return d.weekday()!=6 and 8<=h<=20 and (d>today or (d==today and h>now.hour)) and (booking.car_id,d.isoformat(),h) not in taken
            if not valid(day,booking.requested_hour_24):
                alternatives=[]
                for offset in range(15):
                    d=max(today,day)+timedelta(days=offset)
                    for h in range(8,21):
                        if valid(d,h): alternatives.append({'day':d.isoformat(),'hour':h})
                return {'ok':False,'reason':'Slot unavailable: choose Monday–Saturday, 08:00–20:00 Dubai time; no past or duplicate bookings.','alternatives':alternatives[:3]}
            row=booking.model_dump() | {'requested_day':day.isoformat()}
            rows=[r for r in rows if not (r['user_id']==booking.user_id and not r['requested_day'])]
            rows.append(row)
            f.seek(0)
            writer=csv.DictWriter(f,fieldnames=list(Booking.model_fields))
            writer.writeheader(); writer.writerows(rows); f.truncate()
            f.flush()
            return {'ok':True,'booking':row}
