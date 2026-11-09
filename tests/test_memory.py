import pytest
def test_memory_survives_sessions(tmp_path):
    from src.memory import Memory
    m=Memory(tmp_path/'memory.db')
    m.reset('u','a')
    m.update('u',{'preferred_colors':['white'],'budget_max':60000})
    m.record('u','a','hello','Hi',['H1'])
    m.reset('u','b')
    assert m.profile('u')['budget_max']==60000
    assert m.session('u','a')['last_shown_cars']==['H1']
    assert m.session('u','b')['messages']==[]
    with pytest.raises(PermissionError): m.session('other','a')
