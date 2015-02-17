'''
Created on Feb 10, 2015

@author: joshuaengelsma
@summary: This program immitates the activity of a process manager speaking with
children servers (who each maintain multiple copies of themselves) The process
manager speaks to the servers, and the servers speak back while watching their replicates
@version: Final
'''
import os
import sys
from server_info import server_info
import time
from random import randint
import signal

#structure for process manager to track children servers by name
#key is the server name. server_info model
childrenServers = {}
rmv_proc_flag = False #flag to tell if we should reboot a procedure
grand_children_pids = [] #global copy of grand-children

def process_manager():
    '''
    Method for the process manager. Receives commands, and passes them down to
    the correct server for work.
    '''
    print("Welcome to process manager! Enter a command!\n")
    while True: 
        cmd = sys.stdin.readline().strip()
        if cmd == "quit":
            if len(childrenServers.keys()) != 0:
                print('You need to first abort your servers before quitting')
                continue
            else:
                break;
        cmdParts = cmd.split(' ') #retrieve the user command
        cmdPiece = cmdParts[0]
        
        if len(cmdParts) == 4 and cmdPiece == "createServer": #create server command
            try:
                minProcs = int(cmdParts[1])
                maxProcs = int(cmdParts[2])
            except:
                print('Second and third arguments must be ints')
                continue
            serverName = cmdParts[3]
            if serverName in childrenServers.keys(): #server already exists
                print('You already have a server with this name')
                continue
            read_fd, write_fd = os.pipe() #create a pipe between PM and server
            server_fd_r, server_fd_w = os.pipe() #create a pipe between server and PM
            child_pid = os.fork() #fork of the server process
            if child_pid == 0: #child process -- aka the server spawned by PM
                doMainServerWork(minProcs, maxProcs, serverName, server_fd_w, read_fd)
            elif child_pid > 0: #continue with PM
                childrenServers[serverName] = server_info(serverName, child_pid, minProcs, maxProcs, write_fd, server_fd_r)
        elif len(cmdParts) == 2 and cmdPiece == "abortServer": #abort Server
            serverName = cmdParts[1]
            if serverName not in childrenServers.keys():
                print('Server does not exist for deletion')
                continue
            serverModel = childrenServers[serverName]
            os.write(serverModel.fdWrite, 'k') #tell server to abort
            os.close(serverModel.fdWrite) #close the fds
            os.close(serverModel.fdRead)
            server_pid, exit_status = os.waitpid(serverModel.pid, 0)
            if server_pid == serverModel.pid and exit_status == 0:
                childrenServers.pop(serverName, None)
                print('Server Named: {} and children successfully shutdown'.format(serverName))
            else:
                print('Server was not shut down properly')
        elif len(cmdParts) == 2 and cmdPiece == "createProcess": #create process
            serverName = cmdParts[1]
            if serverName not in childrenServers.keys():
                print('Server does not exist for creating a new process')
                continue
            serverModel = childrenServers[serverName]
            os.write(serverModel.fdWrite, 'c') #tell server to create proc
        elif len(cmdParts) == 2 and cmdPiece == "abortProcess": #abort a process
            serverName = cmdParts[1]
            if serverName not in childrenServers.keys():
                print('Server does not exist for process abortion')
                continue
            serverModel = childrenServers[serverName]
            os.write(serverModel.fdWrite, 'a')
        elif len(cmdParts) == 1 and cmdPiece == "displayStatus": #display status
            for serverKey in childrenServers.keys():
                print('Process Manager: {}'.format(str(os.getpid())))
                print('    Main Server: {} with pid of: {}'.format(serverKey, childrenServers[serverKey].pid))
                os.write(childrenServers[serverKey].fdWrite, 'd')
                grandchildstr = os.read(childrenServers[serverKey].fdRead, 128)
                print(grandchildstr)
                sys.stdout.flush()
        else:
            print('Invalid command {}'.format(usage()))
            
def doMainServerWork(minProcs, maxProcs, serverName, fdWrite, fdRead):
    '''
    @param minProcs: The number of servers to activate during replication
    @param maxProcs: The maximum number of replicated servers that can be added
    @param serverName: Your parent servers name
    @param fdWrite: The write file descriptor to talk with the parent
    @param fdRead: The read file descriptor to receive messages from the parent
    This method is used by each servers to activate numActive copies of itself
    '''
    global rmv_proc_flag
    global grand_children_pids
    rmv_proc_flag = False #every server should start out in non-removal mode
    grand_children_pids = [] #every server should start out with 0 gc
    for i in range(minProcs): #first replicate numActive copies of yourself
        try:
            rand_nbr = randint(1, 10)
            gchild_pid = os.fork()
            if gchild_pid == 0: #child
                if rand_nbr == 1: #10 % of servers will run one minute
                    runForMinute()
                else:
                    runUntilKill()
            elif gchild_pid > 0:
                grand_children_pids.append(gchild_pid)
        except OSError as e:
            print('Error forking copy number {} of server'.format(i+1))
            print(str(e))
    
    signal.signal(signal.SIGCHLD, handleSIGCHLD)
            
    while True: #read from the parent waiting for any children to exit
        try:
            cmd = os.read(fdRead, sys.getsizeof("a")) #read a command from PM
            if cmd == "k":
                rmv_proc_flag = True #we are legitimately going to remove a process
                abortServer(serverName, grand_children_pids, [fdWrite, fdRead])
                rmv_proc_flag = False #we are done removing process
            elif cmd == "c":
                grand_children_pids = createProcess(serverName, maxProcs, grand_children_pids)
            elif cmd == "a":
                rmv_proc_flag = True #we are legitimately going to remove a process
                grand_children_pids = abortProcess(serverName, minProcs, grand_children_pids)
                rmv_proc_flag = False
            elif cmd == "d":
                gchildren = displayGChildren(grand_children_pids)
                os.write(fdWrite, gchildren)
                os.fsync(fdWrite)
        except OSError as e:
            #sigint occurred, so allow server to handle this and then go back to reading
            continue
    
############################### SERVER METHODS ############################
def createProcess(serverName, maxProcs, gchildren):
    '''
    @param serverName: The server who we are adding a procedure too
    @param maxProcs: The max number of procedures that you are allowed to have
    @param gchildren: The current g-children processes
    @return: The updated list of grand childrens
    Method executed by server will create a new process
    '''
    if len(gchildren) == maxProcs:
        print('You cannot add another procedure to: {} without violating max procs'.format(serverName))
    else: #we are allowed to add another procedure
        print('Adding another procedure to: {}'.format(serverName))
        rand_nbr = randint(1, 10)
        new_pid = os.fork()
        if new_pid == 0: #child
            if rand_nbr == 1: #10% of the time you run for one minute
                runForMinute()
            else:
                runUntilKill()
        elif new_pid > 0: #back in server (parent)
            gchildren.append(new_pid) #add the new child
    return gchildren
    
def abortProcess(serverName, minProcs, gchildren):
    '''
    @param serverName: The name of the server you want to abort a proc from
    @param minProcs: The min number of procs you need to have
    @param gchildren: The current grand children of the server
    @return: The updated list of grand children
    Method executed by the server will abort a new process
    '''
    if len(gchildren) == minProcs:
        print('You cannot remove another procedure from: {} without violating min procs'.format(serverName))
    else: #we are allowed to remove a procedure
        print('Removing procedure from {}'.format(serverName))
        pid_to_kill = gchildren[-1] #remove the last child
        os.kill(pid_to_kill, signal.SIGKILL) #kill the grand-child
        gchildren.pop()
    return gchildren
    
def abortServer(serverName, gchildren, fds):
    '''
    @param serverName: The name of the server you wish to abort
    @param gchildren: The g-children that you need to shut down
    @param fds: Server file descriptors to shut down
    Method will shut down myself as the server and all kill all my children
    '''
    os.close(fds[0])
    os.close(fds[1])
    for pid in gchildren: #first kill all of the children!!!!! OH NO
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            continue
    exit(0) #exit from my process 
    
def displayGChildren(gchildren):
    '''
    @param gchildren: The grand-children of this server
    Method will print out all of the grand children
    '''
    printStr = ""
    for child in gchildren:
        printStr += str(child) + ' '
    return("        copies: {}".format(printStr))
    
def handleSIGCHLD(signum, frame):
    '''
    @param signum: The signal number
    @param frame: The frame
    Method handles the situation where a grand - child process just closes down
    '''
    global rmv_proc_flag
    global grand_children_pids
    pid, exit_status = os.wait()
    if rmv_proc_flag:
        return #nothing needs to be handled. server was manually shutting down process
    elif pid not in grand_children_pids:
        return #server must have purposely deleted the process no need to continue
    else:
        print('Child pid shutdown un-expectantly: {} with exit status {}'.format(str(pid), str(exit_status)))
        sys.stdout.flush()
        grand_children_pids.remove(pid) #remove the pid from the list upon termination
        print('Spawing a new child to replace {}'.format(pid))
        rand_nbr = randint(1, 10)
        new_pid = os.fork() #create a new proc to take its place
        if new_pid == -1:
            print('error forking a new process for fault tolerance')
        elif new_pid == 0: #child code
            if rand_nbr == 1:
                runForMinute()
            else:
                runUntilKill()
        elif new_pid > 0: #parent code 
            grand_children_pids.append(new_pid) #add the new pid to the grandchildren of server
                
    
############################### Grand Children #############################
def runUntilKill():
    '''
    grand-children will run this method
    '''
    print('grand-child:{} running forever'.format(os.getpid()))
    while True:
        try:
            time.sleep(2)
        except:
            print('hitting the exception here')
            sys.stdout.flush()
            exit(1)
        
def runForMinute():
    '''
    grand-children will run for one minute only
    '''
    print('grand-child:{} running for 1 minute'.format(os.getpid()))
    rand_nbr = randint(15, 25)
    try:
        time.sleep(rand_nbr) #sleep for random time 25
        exit(1)
    except:
        exit(1)


############################### Usage and Main ###############################
def usage():
    return """
    createServer: createServer min max name
    abortServer: abortServer name
    createProcess: createProcess serverName
    abortProcess: abortProcess serverName
    displayStatus: display current status of the process manager
    """        
    
if __name__ == "__main__":
    process_manager()
        