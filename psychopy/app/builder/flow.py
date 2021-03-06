#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2015 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

"""Dialog classes for the Builder
"""

from __future__ import absolute_import, print_function, division

import sys
import re
import numpy

import wx
from wx.lib import platebtn
import wx.aui, wx.stc

from .. import dialogs
from psychopy import logging, data
from .utils import FileDropTarget
from .dialogs import DlgLoopProperties


canvasColor = [200, 200, 200]  # in prefs? ;-)
routineTimeColor = wx.Colour(50, 100, 200, 200)
staticTimeColor = wx.Colour(200, 50, 50, 100)
nonSlipFill = wx.Colour(150, 200, 150, 255)
nonSlipEdge = wx.Colour(0, 100, 0, 255)
relTimeFill = wx.Colour(200, 150, 150, 255)
relTimeEdge = wx.Colour(200, 50, 50, 255)
routineFlowColor = wx.Colour(200, 150, 150, 255)
darkgrey = wx.Colour(65, 65, 65, 255)
white = wx.Colour(255, 255, 255, 255)
darkblue = wx.Colour(30, 30, 150, 255)
codeSyntaxOkay = wx.Colour(220, 250, 220, 255)  # light green

# regular expression to check for unescaped '$' to indicate code:
_unescapedDollarSign_re = re.compile(r"^\$|[^\\]\$")


class FlowPanel(wx.ScrolledWindow):
    def __init__(self, frame, id=-1):
        """A panel that shows how the routines will fit together
        """
        self.frame=frame
        self.app=frame.app
        self.dpi=self.app.dpi
        wx.ScrolledWindow.__init__(self, frame, id, (0, 0),size = wx.Size(8*self.dpi,3*self.dpi), style=wx.HSCROLL|wx.VSCROLL)
        self.SetBackgroundColour(canvasColor)
        self.needUpdate=True
        self.maxWidth  = 50*self.dpi
        self.maxHeight = 2*self.dpi
        self.mousePos = None
        #if we're adding a loop or routine then add spots to timeline
        #self.drawNearestRoutinePoint = True
        #self.drawNearestLoopPoint = False
        self.pointsToDraw=[] #lists the x-vals of points to draw, eg loop locations
        self.appData = self.app.prefs.appData # for flowSize, showLoopInfoInFlow

        #self.SetAutoLayout(True)
        self.SetScrollRate(self.dpi/4,self.dpi/4)

        # create a PseudoDC to record our drawing
        self.pdc = wx.PseudoDC()
        self.pen_cache = {}
        self.brush_cache = {}
        # vars for handling mouse clicks
        self.hitradius=5
        self.dragid = -1
        self.entryPointPosList = []
        self.entryPointIDlist = []
        self.mode = 'normal'#can also be 'loopPoint1','loopPoint2','routinePoint'
        self.insertingRoutine=""

        #for the context menu
        self.componentFromID = {}#use the ID of the drawn icon to retrieve component (loop or routine)
        self.contextMenuLabels = {'remove': _translate('remove')}
        self.contextMenuItems = ['remove']
        self.contextItemFromID = {}
        self.contextIDFromItem = {}
        for item in self.contextMenuItems:
            id = wx.NewId()
            self.contextItemFromID[id] = item
            self.contextIDFromItem[item] = id

        #self.btnInsertRoutine = wx.Button(self,-1,'Insert Routine', pos=(10,10))
        #self.btnInsertLoop = wx.Button(self,-1,'Insert Loop', pos=(10,30))
        if sys.platform.startswith('linux'): # Localized labels on PlateButton may be corrupted in Ubuntu.
            labelRoutine = 'Insert Routine '
            labelLoop = 'Insert Loop     '
        else:
            labelRoutine = _translate('Insert Routine ')
            labelLoop = _translate('Insert Loop     ')
        self.btnInsertRoutine = platebtn.PlateButton(self,-1,labelRoutine, pos=(10,10))
        self.btnInsertLoop = platebtn.PlateButton(self,-1,labelLoop, pos=(10,30)) #spaces give size for CANCEL

        self.labelTextRed = {'normal': wx.Colour(250,10,10, 250),'hlight':wx.Colour(250,10,10, 250)}
        self.labelTextBlack = {'normal': wx.Colour(0,0,0, 250),'hlight':wx.Colour(250,250,250, 250)}

        # use self.appData['flowSize'] to index a tuple to get a specific value, eg: (4,6,8)[self.appData['flowSize']]
        self.flowMaxSize = 2 # upper limit on increaseSize

        self.draw()

        #bind events
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        self.Bind(wx.EVT_BUTTON, self.onInsertRoutine,self.btnInsertRoutine)
        self.Bind(wx.EVT_BUTTON, self.setLoopPoint1,self.btnInsertLoop)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.SetDropTarget(FileDropTarget(builder = self.frame))

        idClear = wx.NewId()
        self.Bind(wx.EVT_MENU, self.clearMode, id=idClear )
        aTable = wx.AcceleratorTable([
                              (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, idClear)
                              ])
        self.SetAcceleratorTable(aTable)
    def clearMode(self, event=None):
        """If we were in middle of doing something (like inserting routine) then
        end it, allowing user to cancel
        """
        self.mode='normal'
        self.insertingRoutine=None
        for id in self.entryPointIDlist:
            self.pdc.RemoveId(id)
        self.entryPointPosList = []
        self.entryPointIDlist = []
        self.gapsExcluded=[]
        self.draw()
        self.frame.SetStatusText("")
        if sys.platform.startswith('linux'): # Localized labels on PlateButton may be corrupted in Ubuntu.
            self.btnInsertRoutine.SetLabel('Insert Routine')
            self.btnInsertLoop.SetLabel('Insert Loop')
        else:
            self.btnInsertRoutine.SetLabel(_translate('Insert Routine'))
            self.btnInsertLoop.SetLabel(_translate('Insert Loop'))
        self.btnInsertRoutine.SetLabelColor(**self.labelTextBlack)
        self.btnInsertLoop.SetLabelColor(**self.labelTextBlack)
    def ConvertEventCoords(self, event):
        xView, yView = self.GetViewStart()
        xDelta, yDelta = self.GetScrollPixelsPerUnit()
        return (event.GetX() + (xView * xDelta),
            event.GetY() + (yView * yDelta))

    def OffsetRect(self, r):
        """Offset the rectangle, r, to appear in the given position in the window
        """
        xView, yView = self.GetViewStart()
        xDelta, yDelta = self.GetScrollPixelsPerUnit()
        r.OffsetXY(-(xView*xDelta),-(yView*yDelta))

    def onInsertRoutine(self, evt):
        """For when the insert Routine button is pressed - bring up dialog and
        present insertion point on flow line.
        see self.insertRoutine() for further info
        """
        if self.mode.startswith('loopPoint'):
            self.clearMode()
        elif self.mode == 'routine': # clicked again with label now being "Cancel..."
            self.clearMode()
            return
        self.frame.SetStatusText(_translate("Select a Routine to insert (Esc to exit)"))
        menu = wx.Menu()
        self.routinesFromID={}
        id = wx.NewId()
        menu.Append(id, '(new)')
        self.routinesFromID[id] = '(new)'
        wx.EVT_MENU(menu, id, self.insertNewRoutine)
        for routine in self.frame.exp.routines:
            id = wx.NewId()
            menu.Append( id, routine )
            self.routinesFromID[id]=routine
            wx.EVT_MENU( menu, id, self.onInsertRoutineSelect )
        btnPos = self.btnInsertRoutine.GetRect()
        menuPos = (btnPos[0], btnPos[1]+btnPos[3])
        self.PopupMenu( menu, menuPos )
        menu.Bind(wx.EVT_MENU_CLOSE, self.clearMode)
        menu.Destroy() # destroy to avoid mem leak
    def insertNewRoutine(self, event):
        """selecting (new) is a short-cut for: make new routine, insert it into the flow
        """
        newRoutine = self.frame.routinePanel.createNewRoutine(returnName=True)
        if newRoutine:
            self.routinesFromID[event.GetId()] = newRoutine
            self.onInsertRoutineSelect(event)
        else:
            self.clearMode()
    def onInsertRoutineSelect(self,event):
        """User has selected a routine to be entered so bring up the entrypoint marker
        and await mouse button press.
        see self.insertRoutine() for further info
        """
        self.mode='routine'
        if sys.platform.startswith('linux'): # Localized labels on PlateButton may be corrupted in Ubuntu.
            self.btnInsertRoutine.SetLabel('CANCEL Insert')
        else:
            self.btnInsertRoutine.SetLabel(_translate('CANCEL Insert'))
        self.btnInsertRoutine.SetLabelColor(**self.labelTextRed)
        self.frame.SetStatusText(_translate('Click where you want to insert the Routine, or CANCEL insert.'))
        self.insertingRoutine = self.routinesFromID[event.GetId()]
        x = self.getNearestGapPoint(0)
        self.drawEntryPoints([x])
    def insertRoutine(self, ii):
        """Insert a routine into the Flow having determined its name and location

        onInsertRoutine() the button has been pressed so present menu
        onInsertRoutineSelect() user selected the name so present entry points
        OnMouse() user has selected a point on the timeline to insert entry

        """
        self.frame.exp.flow.addRoutine(self.frame.exp.routines[self.insertingRoutine], ii)
        self.frame.addToUndoStack("ADD Routine `%s`" %self.frame.exp.routines[self.insertingRoutine].name)
        #reset flow drawing (remove entry point)
        self.clearMode()

    def setLoopPoint1(self, evt=None):
        """Someone pushed the insert loop button.
        Fetch the dialog
        """
        if self.mode == 'routine':
            self.clearMode()
        elif self.mode.startswith('loopPoint'): # clicked again, label is "Cancel..."
            self.clearMode()
            return
        if sys.platform.startswith('linux'): # Localized labels on PlateButton may be corrupted in Ubuntu.
            self.btnInsertLoop.SetLabel('CANCEL insert')
        else:
            self.btnInsertLoop.SetLabel(_translate('CANCEL insert'))
        self.btnInsertLoop.SetLabelColor(**self.labelTextRed)
        self.mode='loopPoint1'
        self.frame.SetStatusText(_translate('Click where you want the loop to start/end, or CANCEL insert.'))
        x = self.getNearestGapPoint(0)
        self.drawEntryPoints([x])
    def setLoopPoint2(self, evt=None):
        """We've got the location of the first point, waiting to get the second
        """
        self.mode='loopPoint2'
        self.frame.SetStatusText(_translate('Click the other end for the loop'))
        thisPos = self.entryPointPosList[0]
        self.gapsExcluded=[thisPos]
        self.gapsExcluded.extend(self.getGapPointsCrossingStreams(thisPos))
        #is there more than one available point
        x = self.getNearestGapPoint(wx.GetMousePosition()[0]-self.GetScreenPosition()[0],
            exclude=self.gapsExcluded)#exclude point 1, and
        self.drawEntryPoints([self.entryPointPosList[0], x])
        nAvailableGaps= len(self.gapMidPoints)-len(self.gapsExcluded)
        if nAvailableGaps==1:
            self.insertLoop()#there's only one place - go ahead and insert it
    def insertLoop(self, evt=None):
        #bring up listbox to choose the routine to add and/or create a new one
        loopDlg = DlgLoopProperties(frame=self.frame,
            helpUrl = self.app.urls['builder.loops'])
        startII = self.gapMidPoints.index(min(self.entryPointPosList))
        endII = self.gapMidPoints.index(max(self.entryPointPosList))
        if loopDlg.OK:
            handler=loopDlg.currentHandler
            self.frame.exp.flow.addLoop(handler,
                startPos=startII, endPos=endII)
            self.frame.addToUndoStack("ADD Loop `%s` to Flow" %handler.params['name'].val)
        self.clearMode()
        self.draw()
    def increaseSize(self, event=None):
        if self.appData['flowSize'] == self.flowMaxSize:
            self.appData['showLoopInfoInFlow'] = True
        self.appData['flowSize'] = min(self.flowMaxSize, self.appData['flowSize'] + 1)
        self.clearMode() #redraws
    def decreaseSize(self, event=None):
        if self.appData['flowSize'] == 0:
            self.appData['showLoopInfoInFlow'] = False
        self.appData['flowSize'] = max(0, self.appData['flowSize'] - 1)
        self.clearMode() # redraws
    def editLoopProperties(self, event=None, loop=None):
        #add routine points to the timeline
        self.setDrawPoints('loops')
        self.draw()
        if 'conditions' in loop.params.keys():
            condOrig = loop.params['conditions'].val
            condFileOrig = loop.params['conditionsFile'].val
        loopDlg = DlgLoopProperties(frame=self.frame,
            helpUrl = self.app.urls['builder.loops'],
            title=loop.params['name'].val+' Properties', loop=loop)
        if loopDlg.OK:
            prevLoop=loop
            if loopDlg.params['loopType'].val=='staircase':
                loop= loopDlg.stairHandler
            elif loopDlg.params['loopType'].val=='interleaved staircases':
                loop= loopDlg.multiStairHandler
            else:
                loop=loopDlg.trialHandler #['random','sequential', 'fullRandom', ]
            #if the loop is a whole new class then we can't just update the params
            if loop.getType()!=prevLoop.getType():
                #get indices for start and stop points of prev loop
                flow = self.frame.exp.flow
                startII = flow.index(prevLoop.initiator) #find the index of the initiator
                endII = flow.index(prevLoop.terminator)-1 #minus one because initiator will have been deleted
                #remove old loop completely
                flow.removeComponent(prevLoop)
                #finally insert the new loop
                flow.addLoop(loop, startII, endII)
            self.frame.addToUndoStack("EDIT Loop `%s`" %(loop.params['name'].val))
        elif 'conditions' in loop.params.keys():
            loop.params['conditions'].val = condOrig
            loop.params['conditionsFile'].val = condFileOrig
        #remove the points from the timeline
        self.setDrawPoints(None)
        self.draw()

    def OnMouse(self, event):
        x,y = self.ConvertEventCoords(event)
        if self.mode=='normal':
            if event.LeftDown():
                icons = self.pdc.FindObjectsByBBox(x, y)
                for thisIcon in icons:#might intersect several and only one has a callback
                    if thisIcon in self.componentFromID:
                        comp=self.componentFromID[thisIcon]
                        if comp.getType() in ['StairHandler', 'TrialHandler', 'MultiStairHandler']:
                            self.editLoopProperties(loop=comp)
                        if comp.getType() == 'Routine':
                            self.frame.routinePanel.setCurrentRoutine(routine=comp)
            elif event.RightDown():
                icons = self.pdc.FindObjectsByBBox(x, y)
                comp=None
                for thisIcon in icons:#might intersect several and only one has a callback
                    if thisIcon in self.componentFromID:
                        #loop through comps looking for Routine, or a Loop if no routine
                        thisComp=self.componentFromID[thisIcon]
                        if thisComp.getType() in ['StairHandler', 'TrialHandler', 'MultiStairHandler']:
                            comp=thisComp#use this if we don't find a routine
                            icon=thisIcon
                        if thisComp.getType() == 'Routine':
                            comp=thisComp
                            icon=thisIcon
                            break#we've found a Routine so stop looking
                try:
                    self._menuComponentID=icon
                    self.showContextMenu(self._menuComponentID,
                        xy=wx.Point(x+self.GetPosition()[0],y+self.GetPosition()[1]))
                except UnboundLocalError:
                    # right click but not on an icon
                    self.Refresh() # might as well do something
        elif self.mode=='routine':
            if event.LeftDown():
                self.insertRoutine(ii=self.gapMidPoints.index(self.entryPointPosList[0]))
            else:#move spot if needed
                point = self.getNearestGapPoint(mouseX=x)
                self.drawEntryPoints([point])
        elif self.mode=='loopPoint1':
            if event.LeftDown():
                self.setLoopPoint2()
            else:#move spot if needed
                point = self.getNearestGapPoint(mouseX=x)
                self.drawEntryPoints([point])
        elif self.mode=='loopPoint2':
            if event.LeftDown():
                self.insertLoop()
            else:#move spot if needed
                point = self.getNearestGapPoint(mouseX=x, exclude=self.gapsExcluded)
                self.drawEntryPoints([self.entryPointPosList[0], point])
    def getNearestGapPoint(self, mouseX, exclude=[]):
        """Get gap that is nearest to a particular mouse location
        """
        d=1000000000
        nearest=None
        for point in self.gapMidPoints:
            if point in exclude:
                continue
            if (point-mouseX)**2 < d:
                d=(point-mouseX)**2
                nearest=point
        return nearest
    def getGapPointsCrossingStreams(self,gapPoint):
        """For a given gap point, identify the gap points that are
        excluded by crossing a loop line
        """
        gapArray=numpy.array(self.gapMidPoints)
        nestLevels=numpy.array(self.gapNestLevels)
        thisLevel=nestLevels[gapArray==gapPoint]
        invalidGaps= (gapArray[nestLevels!=thisLevel]).tolist()
        return invalidGaps
    def showContextMenu(self, component, xy):
        menu = wx.Menu()
        for item in self.contextMenuItems:
            id = self.contextIDFromItem[item]
            menu.Append( id, self.contextMenuLabels[item] )
            wx.EVT_MENU( menu, id, self.onContextSelect )
        self.frame.PopupMenu( menu, xy )
        menu.Destroy() # destroy to avoid mem leak
    def onContextSelect(self, event):
        """Perform a given action on the component chosen
        """
        #get ID
        op = self.contextItemFromID[event.GetId()]
        compID=self._menuComponentID #the ID is also the index to the element in the flow list
        flow = self.frame.exp.flow
        component=flow[compID]
        #if we have a Loop Initiator, remove the whole loop
        if component.getType()=='LoopInitiator':
            component = component.loop
        if op=='remove':
            self.removeComponent(component, compID)
            self.frame.addToUndoStack("REMOVE `%s` from Flow" %component.params['name'])
        if op=='rename':
            print('rename is not implemented yet')
            #if component is a loop: DlgLoopProperties
            #elif component is a routine: DlgRoutineProperties
        self.draw()
        self._menuComponentID=None
    def removeComponent(self, component, compID):
        """Remove either a Routine or a Loop from the Flow
        """
        flow=self.frame.exp.flow
        if component.getType()=='Routine':
            #check whether this will cause a collapsed loop
            #prev and next elements on flow are a loop init/end
            prevIsLoop=nextIsLoop=False
            if compID>0:#there is at least one preceding
                prevIsLoop = (flow[compID-1]).getType()=='LoopInitiator'
            if len(flow)>(compID+1):#there is at least one more compon
                nextIsLoop = (flow[compID+1]).getType()=='LoopTerminator'
            if prevIsLoop and nextIsLoop:
                loop=flow[compID+1].loop#because flow[compID+1] is a terminator
                warnDlg = dialogs.MessageDialog(parent=self.frame,
                    message=_translate('The "%s" Loop is about to be deleted as well (by collapsing). OK to proceed?') %loop.params['name'],
                    type='Warning', title=_translate('Impending Loop collapse'))
                resp=warnDlg.ShowModal()
                if resp in [wx.ID_CANCEL, wx.ID_NO]:
                    return#abort
                elif resp==wx.ID_YES:
                    #make some recursive calls to this same method until success
                    self.removeComponent(loop, compID )#remove the loop first
                    self.removeComponent(component, compID-1)#because the loop has been removed ID is now one less
                    return #because we would have done the removal in final successful call
        # remove name from namespace only if it's a loop (which exists only in the flow)
        elif 'conditionsFile' in component.params.keys():
            conditionsFile = component.params['conditionsFile'].val
            if conditionsFile and conditionsFile not in ['None','']:
                try:
                    trialList, fieldNames = data.importConditions(conditionsFile, returnFieldNames=True)
                    for fname in fieldNames:
                        self.frame.exp.namespace.remove(fname)
                except:
                    logging.debug("Conditions file %s couldn't be found so names not removed from namespace" % conditionsFile)
            self.frame.exp.namespace.remove(component.params['name'].val)
        #perform the actual removal
        flow.removeComponent(component, id=compID)

    def OnPaint(self, event):
        # Create a buffered paint DC.  It will create the real
        # wx.PaintDC and then blit the bitmap to it when dc is
        # deleted.
        dc = wx.GCDC(wx.BufferedPaintDC(self))
        # use PrepareDC to set position correctly
        self.PrepareDC(dc)
        # we need to clear the dc BEFORE calling PrepareDC
        bg = wx.Brush(self.GetBackgroundColour())
        dc.SetBackground(bg)
        dc.Clear()
        # create a clipping rect from our position and size
        # and the Update Region
        xv, yv = self.GetViewStart()
        dx, dy = self.GetScrollPixelsPerUnit()
        x, y   = (xv * dx, yv * dy)
        rgn = self.GetUpdateRegion()
        rgn.Offset(x,y)
        r = rgn.GetBox()
        # draw to the dc using the calculated clipping rect
        self.pdc.DrawToDCClipped(dc,r)

    def draw(self, evt=None):
        """This is the main function for drawing the Flow panel.
        It should be called whenever something changes in the exp.

        This then makes calls to other drawing functions, like drawEntryPoints...
        """
        if not hasattr(self.frame, 'exp'):
            return#we haven't yet added an exp
        expFlow = self.frame.exp.flow #retrieve the current flow from the experiment
        pdc=self.pdc

        self.componentFromID={}#use the ID of the drawn icon to retrieve component (loop or routine)

        pdc.Clear()#clear the screen
        pdc.RemoveAll()#clear all objects (icon buttons)
        pdc.BeginDrawing()

        font = self.GetFont()

        #draw the main time line
        self.linePos = (2.5*self.dpi,0.5*self.dpi) #x,y of start
        gap = self.dpi / (6, 4, 2) [self.appData['flowSize']]
        dLoopToBaseLine = (15, 25, 43) [self.appData['flowSize']]
        dBetweenLoops = (20, 24, 30) [self.appData['flowSize']]

        #guess virtual size; nRoutines wide by nLoops high
        #make bigger than needed and shrink later
        nRoutines = len(expFlow)
        nLoops = 0
        for entry in expFlow:
            if entry.getType()=='LoopInitiator':
                nLoops += 1
        self.SetVirtualSize(size=(nRoutines*self.dpi*2, nLoops*dBetweenLoops+dLoopToBaseLine*3))

        #step through components in flow, get spacing info from text size, etc
        currX=self.linePos[0]
        lineId=wx.NewId()
        pdc.DrawLine(x1=self.linePos[0]-gap,y1=self.linePos[1],x2=self.linePos[0],y2=self.linePos[1])
        self.loops={}#NB the loop is itself the key!? and the value is further info about it
        nestLevel=0
        maxNestLevel=0
        self.gapMidPoints=[currX-gap/2]
        self.gapNestLevels=[0]
        for ii, entry in enumerate(expFlow):
            if entry.getType()=='LoopInitiator':
                self.loops[entry.loop]={'init':currX,'nest':nestLevel, 'id':ii}#NB the loop is itself the dict key!?
                nestLevel+=1#start of loop so increment level of nesting
                maxNestLevel = max(nestLevel, maxNestLevel)
            elif entry.getType()=='LoopTerminator':
                self.loops[entry.loop]['term']=currX #NB the loop is itself the dict key!
                nestLevel-=1#end of loop so decrement level of nesting
            elif entry.getType()=='Routine':
                # just get currX based on text size, don't draw anything yet:
                currX = self.drawFlowRoutine(pdc,entry, id=ii,pos=[currX,self.linePos[1]-10], draw=False)
            self.gapMidPoints.append(currX+gap/2)
            self.gapNestLevels.append(nestLevel)
            pdc.SetId(lineId)
            pdc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
            pdc.DrawLine(x1=currX,y1=self.linePos[1],x2=currX+gap,y2=self.linePos[1])
            currX+=gap
        lineRect = wx.Rect(self.linePos[0]-2, self.linePos[1]-2, currX-self.linePos[0]+2, 4)
        pdc.SetIdBounds(lineId,lineRect)

        # draw the loops first:
        maxHeight = 0
        for thisLoop in self.loops:
            thisInit = self.loops[thisLoop]['init']
            thisTerm = self.loops[thisLoop]['term']
            thisNest = maxNestLevel-self.loops[thisLoop]['nest']-1
            thisId = self.loops[thisLoop]['id']
            height = self.linePos[1]+dLoopToBaseLine + thisNest*dBetweenLoops
            self.drawLoop(pdc,thisLoop,id=thisId,
                        startX=thisInit, endX=thisTerm,
                        base=self.linePos[1],height=height)
            self.drawLoopStart(pdc,pos=[thisInit,self.linePos[1]])
            self.drawLoopEnd(pdc,pos=[thisTerm,self.linePos[1]])
            if height > maxHeight:
                maxHeight=height

        # draw routines second (over loop lines):
        currX=self.linePos[0]
        for ii, entry in enumerate(expFlow):
            if entry.getType()=='Routine':
                currX = self.drawFlowRoutine(pdc,entry, id=ii,pos=[currX,self.linePos[1]-10])
            pdc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
            pdc.DrawLine(x1=currX,y1=self.linePos[1],x2=currX+gap,y2=self.linePos[1])
            currX += gap

        self.SetVirtualSize(size=(currX+100, maxHeight+50))

        #draw all possible locations for routines DEPRECATED SINCE 1.62 because not drawing those
        #for n, xPos in enumerate(self.pointsToDraw):
        #   font.SetPointSize(600/self.dpi)
        #   self.SetFont(font); pdc.SetFont(font)
        #   w,h = self.GetFullTextExtent(str(len(self.pointsToDraw)))[0:2]
        #   pdc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
        #   pdc.SetBrush(wx.Brush(wx.Colour(0,0,0,255)))
        #   pdc.DrawCircle(xPos,self.linePos[1], w+2)
        #   pdc.SetTextForeground([255,255,255])
        #   pdc.DrawText(str(n), xPos-w/2, self.linePos[1]-h/2)

        self.drawLineStart(pdc, (self.linePos[0]-gap,self.linePos[1]))
        self.drawLineEnd(pdc, (currX, self.linePos[1]))

        pdc.EndDrawing()
        self.Refresh()#refresh the visible window after drawing (using OnPaint)
    def drawEntryPoints(self, posList):
        ptSize = (3,4,5)[self.appData['flowSize']]
        for n, pos in enumerate(posList):
            if n>=len(self.entryPointPosList):
                #draw for first time
                id = wx.NewId()
                self.entryPointIDlist.append(id)
                self.pdc.SetId(id)
                self.pdc.SetBrush(wx.Brush(wx.Colour(0,0,0,255)))
                self.pdc.DrawCircle(pos,self.linePos[1], ptSize)
                r = self.pdc.GetIdBounds(id)
                self.OffsetRect(r)
                self.RefreshRect(r, False)
            elif pos == self.entryPointPosList[n]:
                pass#nothing to see here, move along please :-)
            else:
                #move to new position
                dx = pos-self.entryPointPosList[n]
                dy = 0
                r = self.pdc.GetIdBounds(self.entryPointIDlist[n])
                self.pdc.TranslateId(self.entryPointIDlist[n], dx, dy)
                r2 = self.pdc.GetIdBounds(self.entryPointIDlist[n])
                rectToRedraw = r.Union(r2)#combine old and new locations to get redraw area
                rectToRedraw.Inflate(4,4)
                self.OffsetRect(rectToRedraw)
                self.RefreshRect(rectToRedraw, False)

        self.entryPointPosList=posList
        self.Refresh()#refresh the visible window after drawing (using OnPaint)

    def setDrawPoints(self, ptType, startPoint=None):
        """Set the points of 'routines', 'loops', or None
        """
        if ptType=='routines':
            self.pointsToDraw=self.gapMidPoints
        elif ptType=='loops':
            self.pointsToDraw=self.gapMidPoints
        else:
            self.pointsToDraw=[]
    def drawLineStart(self, dc, pos):
        #draw bar at start of timeline; circle looked bad, offset vertically
        ptSize = (3,3,4)[self.appData['flowSize']]
        dc.SetBrush(wx.Brush(wx.Colour(0,0,0, 255)))
        dc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
        dc.DrawPolygon([[0,-ptSize],[1,-ptSize],[1,ptSize], [0,ptSize]], pos[0],pos[1])
    def drawLineEnd(self, dc, pos):
        #draws arrow at end of timeline
        #tmpId = wx.NewId()
        #dc.SetId(tmpId)
        dc.SetBrush(wx.Brush(wx.Colour(0,0,0, 255)))
        dc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
        dc.DrawPolygon([[0,-3],[5,0],[0,3]], pos[0],pos[1])
        #dc.SetIdBounds(tmpId,wx.Rect(pos[0],pos[1]+3,5,6))
    def drawLoopEnd(self, dc, pos, downwards=True):
        # define the right side of a loop but draw nothing
        # idea: might want a wxID for grabbing and relocating the loop endpoint
        tmpId = wx.NewId()
        dc.SetId(tmpId)
        #dc.SetBrush(wx.Brush(wx.Colour(0,0,0, 250)))
        #dc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
        size = (3,4,5)[self.appData['flowSize']]
        #if downwards: dc.DrawPolygon([[size,0],[0,size],[-size,0]], pos[0],pos[1]+2*size)#points down
        #else: dc.DrawPolygon([[size,size],[0,0],[-size,size]], pos[0],pos[1]-3*size)#points up
        dc.SetIdBounds(tmpId,wx.Rect(pos[0]-size,pos[1]-size,2*size,2*size))
        return
    def drawLoopStart(self, dc, pos, downwards=True):
        # draws direction arrow on left side of a loop
        tmpId = wx.NewId()
        dc.SetId(tmpId)
        dc.SetBrush(wx.Brush(wx.Colour(0,0,0, 250)))
        dc.SetPen(wx.Pen(wx.Colour(0,0,0, 255)))
        size = (3,4,5)[self.appData['flowSize']]
        offset = (3,2,0)[self.appData['flowSize']]
        if downwards:
            dc.DrawPolygon([[size,size],[0,0],[-size,size]], pos[0],pos[1]+3*size-offset)#points up
        else:
            dc.DrawPolygon([[size,0],[0,size],[-size,0]], pos[0],pos[1]-4*size)#points down
        dc.SetIdBounds(tmpId,wx.Rect(pos[0]-size,pos[1]-size,2*size,2*size))

    def drawFlowRoutine(self,dc,routine,id,pos=[0,0], draw=True):
        """Draw a box to show a routine on the timeline
        draw=False is for a dry-run, esp to compute and return size information without drawing or setting a pdc ID
        """
        name = routine.name
        if self.appData['flowSize']==0 and len(name) > 5:
            name = ' '+name[:4]+'..'
        else:
            name = ' '+name+' '
        if draw:
            dc.SetId(id)
        font = self.GetFont()
        if sys.platform=='darwin':
            fontSizeDelta = (9,6,0)[self.appData['flowSize']]
            font.SetPointSize(1400/self.dpi-fontSizeDelta)
        elif sys.platform.startswith('linux'):
            fontSizeDelta = (6,4,0)[self.appData['flowSize']]
            font.SetPointSize(1400/self.dpi-fontSizeDelta)
        else:
            fontSizeDelta = (8,4,0)[self.appData['flowSize']]
            font.SetPointSize(1000/self.dpi-fontSizeDelta)

        maxTime, nonSlip = routine.getMaxTime()
        if nonSlip:
            rgbFill=nonSlipFill
            rgbEdge=nonSlipEdge
        else:
            rgbFill=relTimeFill
            rgbEdge=relTimeEdge

        #get size based on text
        self.SetFont(font)
        if draw: dc.SetFont(font)
        w,h = self.GetFullTextExtent(name)[0:2]
        pad = (5,10,20)[self.appData['flowSize']]
        #draw box
        pos[1] += 2-self.appData['flowSize']
        rect = wx.Rect(pos[0], pos[1], w+pad,h+pad)
        endX = pos[0]+w+pad
        #the edge should match the text
        if draw:
            dc.SetPen(wx.Pen(wx.Colour(rgbEdge[0],rgbEdge[1],rgbEdge[2], wx.ALPHA_OPAQUE)))
            dc.SetBrush(wx.Brush(rgbFill))
            dc.DrawRoundedRectangleRect(rect, (4,6,8)[self.appData['flowSize']])
            #draw text
            dc.SetTextForeground(rgbEdge)
            dc.DrawLabel(name, rect, alignment = wx.ALIGN_CENTRE)
            if nonSlip and self.appData['flowSize']!=0:
                font.SetPointSize(font.GetPointSize()*0.6)
                dc.SetFont(font)
                dc.DrawLabel("(%.2fs)" %maxTime,
                    rect, alignment = wx.ALIGN_CENTRE|wx.ALIGN_BOTTOM)

            self.componentFromID[id]=routine
            #set the area for this component
            dc.SetIdBounds(id,rect)

        return endX

    def drawLoop(self,dc,loop,id, startX,endX,
            base,height,rgb=[0,0,0], downwards=True):
        if downwards: up=-1
        else: up=+1

        #draw loop itself, as transparent rect with curved corners
        tmpId = wx.NewId()
        dc.SetId(tmpId)
        curve = (6, 11, 15)[self.appData['flowSize']] #extra distance, in both h and w for curve
        yy = [base,height+curve*up,height+curve*up/2,height] # for area
        r,g,b=rgb
        dc.SetPen(wx.Pen(wx.Colour(r, g, b, 200)))
        vertOffset=0 # 1 is interesting too
        area = wx.Rect(startX, base+vertOffset, endX-startX, max(yy)-min(yy))
        dc.SetBrush(wx.Brush(wx.Colour(0,0,0,0),style=wx.TRANSPARENT)) # transparent
        dc.DrawRoundedRectangleRect(area, curve) # draws outline
        dc.SetIdBounds(tmpId, area)

        #add a name label, loop info, except at smallest size
        name = loop.params['name'].val
        if self.appData['showLoopInfoInFlow'] and not self.appData['flowSize']==0:
            if 'conditions' in loop.params.keys() and loop.params['conditions'].val:
                xnumTrials = 'x'+str(len(loop.params['conditions'].val))
            else: xnumTrials = ''
            name += '  ('+str(loop.params['nReps'].val)+xnumTrials
            abbrev = ['', {'random': 'rand.', 'sequential': 'sequ.', 'fullRandom':'f-ran.',
                      'staircase': 'stair.', 'interleaved staircases': "int-str."},
                      {'random': 'random', 'sequential': 'sequential', 'fullRandom':'fullRandom',
                      'staircase': 'staircase', 'interleaved staircases': "interl'vd stairs"}]
            name += ' '+abbrev[self.appData['flowSize']][loop.params['loopType'].val]+')'
        if self.appData['flowSize']==0:
            if len(name) > 9:
                name = ' '+name[:8]+'..'
            else: name = ' '+name[:9]
        else:
            name = ' '+name+' '

        dc.SetId(id)
        font = self.GetFont()
        if sys.platform=='darwin':
            basePtSize = (650,750,900)[self.appData['flowSize']]
        elif sys.platform.startswith('linux'):
            basePtSize = (750,850,1000)[self.appData['flowSize']]
        else:
            basePtSize = (700,750,800)[self.appData['flowSize']]
        font.SetPointSize(basePtSize/self.dpi)
        self.SetFont(font)
        dc.SetFont(font)

        #get size based on text
        pad = (5,8,10)[self.appData['flowSize']]
        w,h = self.GetFullTextExtent(name)[0:2]
        x = startX+(endX-startX)/2-w/2-pad/2
        y = (height-h/2)

        #draw box
        rect = wx.Rect(x, y, w+pad,h+pad)
        #the edge should match the text
        dc.SetPen(wx.Pen(wx.Colour(r, g, b, 100)))
        #try to make the loop fill brighter than the background canvas:
        dc.SetBrush(wx.Brush(wx.Colour(235,235,235, 250)))

        dc.DrawRoundedRectangleRect(rect, (4,6,8)[self.appData['flowSize']])
        #draw text
        dc.SetTextForeground([r,g,b])
        dc.DrawText(name, x+pad/2, y+pad/2)

        self.componentFromID[id]=loop
        #set the area for this component
        dc.SetIdBounds(id,rect)
