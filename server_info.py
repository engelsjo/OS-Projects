'''
Created on Feb 10, 2015

@author: joshuaengelsma
'''

class server_info(object):
    '''
    class holds information for a spawned server
    '''


    def __init__(self, serverName, pid, minProcs, maxProcs, fdWrite, fdRead):
        '''
        Set up my model data
        '''
        self.name = serverName
        self.pid = pid
        self.minProcs = minProcs
        self.maxProcs = maxProcs
        self.fdWrite = fdWrite
        self.fdRead = fdRead
        