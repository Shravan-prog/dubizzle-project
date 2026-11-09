import json
import sqlite3
from src.schemas import Preferences

class Memory:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS user_profiles (user_id TEXT PRIMARY KEY, profile TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, messages TEXT NOT NULL, last_shown_cars TEXT NOT NULL)')

    def connect(self): return sqlite3.connect(self.path,timeout=10)

    def profile(self,user):
        with self.connect() as db:
            row=db.execute('SELECT profile FROM user_profiles WHERE user_id=?',(user,)).fetchone()
        return json.loads(row[0]) if row else Preferences().model_dump()

    def update(self,user,values):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT profile FROM user_profiles WHERE user_id=?',(user,)).fetchone()
            profile=json.loads(row[0]) if row else Preferences().model_dump()
            profile.update(values)
            profile=Preferences(**profile).model_dump()
            if profile['budget_min'] is not None and profile['budget_max'] is not None and profile['budget_min']>profile['budget_max']: raise ValueError('Invalid budget range')
            db.execute('INSERT INTO user_profiles VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET profile=excluded.profile',(user,json.dumps(profile)))
        return profile

    def session(self,user,session):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?,?)',(session,user,'[]','[]'))
            row=db.execute('SELECT user_id,messages,last_shown_cars FROM sessions WHERE session_id=?',(session,)).fetchone()
        if row[0]!=user: raise PermissionError('Session belongs to another user')
        return {'messages':json.loads(row[1]),'last_shown_cars':json.loads(row[2])}

    def reset(self,user,session):
        self.session(user,session)
        with self.connect() as db: db.execute("UPDATE sessions SET messages='[]',last_shown_cars='[]' WHERE session_id=?",(session,))

    def record(self,user,session,message,reply,ids):
        state=self.session(user,session)
        messages=state['messages']+[{'role':'user','content':message},{'role':'assistant','content':reply}]
        with self.connect() as db: db.execute('UPDATE sessions SET messages=?,last_shown_cars=? WHERE session_id=?',(json.dumps(messages),json.dumps(ids),session))
