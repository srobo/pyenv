import subprocess, sys
import types
import logging

import robot

import addhack
from time_event import TimeoutEvent
from poll import Poll, TimePoll
from games import *
from colours import *

class EventInfo:
    def __init__(self, evtree):
        self.evtree = evtree
        self.pop_tree()

    def __eq__(self, obj):
        def ev_cmp(e):
            if isinstance(e, list):
                for x in e:
                    if ev_cmp(x):
                        return True
                return False
            else:
                return e == obj

        return ev_cmp(self.evtree)

    def pop_tree(self):
        def add_events(ev):
            if isinstance(ev, list):
                for e in ev:
                    add_events(e)
            else:
                ev.add_info(self)

        # Recusively add events :-O
        if self.evtree != None:
            add_events(self.evtree)

class Coroutine:
    def __init__(self, generator, name = ""):
        self.name = name
        self.first_run = True

        self.polls = []
        self.stack = [generator]
        self.event = None

    def configure_event(self):
        "Configure robot.event to represent the last event"
        ev = EventInfo(self.event)
        __builtins__["event"] = ev
        robot.event = ev

    def poll(self):
        "Call poll functions."
        for p in xrange(0, len(self.polls)):
            poll = self.polls[p]

            result = None

            try:
                result = poll.next()
            except StopIteration:
                # mark poll for removal
                self.polls[p] = None

            if result != None:
                # We have an event
                self.event = result
                # All polls are now invalid
                self.polls = []
                return
            
        # Remove polls that have chosen to remove themselves
        self.polls = [x for x in self.polls if x != None]

        if len(self.polls) == 0:
            self.event = TimeoutEvent(1)

    def proc(self):
        "Call the generator and get new polls."

        if self.event == None and (not self.first_run):
            return

        self.first_run = False

        self.configure_event()

        #Run the command on the top of the stack
        #If the generator is done, try the next one
        #If there are no generators, throw a StopIteration
        while True:
            try:
                results = self.stack[-1].next()
                break
            except StopIteration:
                #Remove the current function from the stack
                self.stack.pop()
                if len(self.stack) == 0:
                    #This coroutine has finished completely
                    raise StopIteration

        self.event = None

        if isinstance(results, types.TupleType):
            results = list(results)
        else:
            results = [results]

        if results == [None]:
            # Function returned or yielded nothing
            return

        if results[0].__class__ == types.FunctionType:
            #Push the function onto the stack
            #Passing the rest of the yield as arguments
            self.stack.append(results[0](*results[1:]))
            self.first_run = True
            self.proc()
        else:
            for result in results:
                if result.__class__ == types.GeneratorType:
                    self.polls.append(result)
                elif isinstance(result, int) or isinstance(result, float):
                    self.polls.append( TimePoll(result) )
                elif isinstance(result,Poll):
                    self.polls.append(result)
                else:
                    print "WARNING: Ignoring poll", str(result)
                    print type(result)

def sync():
    "Sync to disk every 5 seconds"
    while True:
        yield 5
        sys.stdout.flush()
        subprocess.Popen("sync").wait()

class Trampoline:
    def __init__(self, colour=RED, game = GOLF):
        self.colour = colour
        self.game = game

    def schedule(self):
        """
        Manage coroutines.
        Ask each coroutine to poll, then execute them.
        """
        coroutines = []

        # sync to disk every 5 seconds:
        coroutines.append( Coroutine( sync(), name = "sync" ) )

        robot.event = None
        __builtins__["event"] = None

        while True:
            for i in range(0, len(coroutines)): 
                "Call all the coroutines"
                c = coroutines[i]

                try:
                    c.proc()
                except StopIteration:
                    # Mark the coroutine for removal
                    print "Removing coroutine"
                    coroutines[i] = None

            # Remove dead coroutines
            while None in coroutines:
                coroutines.remove(None)

            for c in coroutines:
                "Poll all the coroutines"
                c.poll()

            # Add new coroutines into the mix:
            for c in addhack.get_coroutines():
                coroutines.append( Coroutine( c[0](*c[1],**c[2]) ) )
            addhack.clear_coroutines()

if __name__ == "__main__":
    import sys, os, os.path
    sys.path.insert(0, os.path.join(os.curdir, "robot.zip"))
    import robot
    t = Trampoline()
    t.schedule()
