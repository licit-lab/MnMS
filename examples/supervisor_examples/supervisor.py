from mnms.simulation import Supervisor



supervisor = Supervisor()
supervisor.load_config('config.ini')
print(supervisor.graph)
