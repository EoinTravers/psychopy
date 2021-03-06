#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2015 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

"""Dialog classes for the Builder, including ParamCtrls
"""

from __future__ import absolute_import, print_function, division

import os
import copy
import numpy
import re
import wx
from wx.lib import flatnotebook

from ... import dialogs
from .. import validators, experiment
from .dlgsConditions import DlgConditions
from .dlgsCode import DlgCodeComponentProperties, CodeBox
from psychopy import data, logging


_unescapedDollarSign_re = re.compile(r"^\$|[^\\]\$")

_localized = {
    # strings for all allowedVals (from all components) go here:
        'linear': _translate('linear'), 'nearest': _translate('nearest'),  # interpolation
        'rgb': 'rgb', 'dkl': 'dkl', 'lms': 'lms', 'hsv':'hsv',  # not translated
        'last key' : _translate('last key'), 'first key': _translate('first key'),
        'all keys': _translate('all keys'), 'nothing': _translate('nothing'),
        'last button' : _translate('last button'), 'first button': _translate('first button'),
        'all buttons': _translate('all buttons'),
        'final': _translate('final'), 'on click': _translate('on click'), 'every frame': _translate('every frame'),
        'never': _translate('never'),
        'from exp settings': _translate('from exp settings'), 'from prefs': _translate('from preferences'),
        'circle': _translate('circle'), 'square': _translate('square'),  # dots
        'direction': _translate('direction'), 'position': _translate('position'), 'walk': _translate('walk'),  # dots
        'same': _translate('same'), 'different': _translate('different'),  # dots
        'experiment': _translate('Experiment'),
        # startType & stopType:
        'time (s)': _translate('time (s)'), 'frame N': _translate('frame N'), 'condition': _translate('condition'),
        'duration (s)': _translate('duration (s)'), 'duration (frames)': _translate('duration (frames)'),
        # not translated:
        'pix': 'pix', 'deg': 'deg', 'cm': 'cm', 'norm': 'norm', 'height': 'height',
        '32': '32', '64': '64', '128': '128', '256': '256', '512': '512',  # tex resolution
        'routine': 'Routine',
    # strings for allowedUpdates:
        'constant': _translate('constant'),
        'set every repeat': _translate('set every repeat'),
        'set every frame': _translate('set every frame'),
    # strings for allowedVals in settings:
        'add': _translate('add'), 'avg': _translate('average'), # blend mode
        'use prefs': _translate('use preferences'),
    # logging level:
        'debug': _translate('debug'), 'info': _translate('info'), 'exp': _translate('exp'),
        'data': _translate('data'), 'warning': _translate('warning'), 'error': _translate('error'),
    # Experiment info dialog:
        'Field': _translate('Field'), 'Default': _translate('Default'),
    }


class ParamCtrls(object):
    def __init__(self, dlg, label, param, parent, fieldName,
                 browse=False, noCtrls=False, advanced=False, appPrefs=None):
        """Create a set of ctrls for a particular Component Parameter, to be
        used in Component Properties dialogs. These need to be positioned
        by the calling dlg.

        e.g.::

            param = experiment.Param(val='boo', valType='str')
            ctrls=ParamCtrls(dlg=self, label=fieldName,param=param)
            self.paramCtrls[fieldName] = ctrls #keep track of them in the dlg
            sizer.Add(ctrls.nameCtrl, (currRow,0), (1,1),wx.ALIGN_RIGHT )
            sizer.Add(ctrls.valueCtrl, (currRow,1) )
            #these are optional (the parameter might be None)
            if ctrls.typeCtrl: sizer.Add(ctrls.typeCtrl, (currRow,2) )
            if ctrls.updateCtrl: sizer.Add(ctrls.updateCtrl, (currRow,3))

        If browse is True then a browseCtrl will be added (you need to bind events yourself)
        If noCtrls is True then no actual wx widgets are made, but attribute names are created

        `fieldName`'s value is always in en_US, and never for display, whereas `label`
        is only for display and can be translated or tweaked (e.g., add '$').
        Component._localized.keys() are `fieldName`s, and .values() are `label`s.
        """
        self.param = param
        self.dlg = dlg
        self.dpi=self.dlg.dpi
        self.valueWidth = self.dpi*3.5
        #try to find the experiment
        self.exp=None
        tryForExp = self.dlg
        while self.exp is None:
            if hasattr(tryForExp,'frame'):
                self.exp=tryForExp.frame.exp
            else:
                try:
                    tryForExp=tryForExp.parent#try going up a level
                except:
                    tryForExp.parent

        #param has the fields:
        #val, valType, allowedVals=[],allowedTypes=[], hint="", updates=None, allowedUpdates=None
        # we need the following
        self.nameCtrl = self.valueCtrl = self.typeCtrl = self.updateCtrl = None
        self.browseCtrl = None
        if noCtrls:
            return  # we don't need to do any more

        if type(param.val)==numpy.ndarray:
            initial=param.val.tolist() #convert numpy arrays to lists
        #labelLength = wx.Size(self.dpi*2,self.dpi*2/3)#was 8*until v0.91.4
        if param.valType == 'code' and fieldName not in ['name', 'Experiment info']:
            label += ' $'
        self.nameCtrl = wx.StaticText(parent,-1,label,size=None,style=wx.ALIGN_RIGHT)

        if fieldName in ['text', 'customize_everything']:
            #for text input we need a bigger (multiline) box
            if fieldName == 'customize_everything':
                sx,sy = 300,400
            else:
                sx,sy = 100, 100
            self.valueCtrl = CodeBox(parent,-1,
                 pos=wx.DefaultPosition, size=wx.Size(sx,sy),#set the viewer to be small, then it will increase with wx.aui control
                 style=0, prefs=appPrefs)
            if len(param.val):
                self.valueCtrl.AddText(unicode(param.val))
            if fieldName == 'text':
                self.valueCtrl.SetFocus()
        elif fieldName == 'Experiment info':
            #for expInfo convert from a string to the list-of-dicts
            val = self.expInfoToListWidget(param.val)
            self.valueCtrl = dialogs.ListWidget(parent, val, order=['Field','Default'])
        elif param.valType=='extendedCode':
            self.valueCtrl = CodeBox(parent,-1,
                 pos=wx.DefaultPosition, size=wx.Size(100,100),#set the viewer to be small, then it will increase with wx.aui control
                 style=0, prefs=appPrefs)
            if len(param.val):
                self.valueCtrl.AddText(unicode(param.val))
            #code input fields one day change these to wx.stc fields?
            #self.valueCtrl = wx.TextCtrl(parent,-1,unicode(param.val),
            #    style=wx.TE_MULTILINE,
            #    size=wx.Size(self.valueWidth*2,160))
        elif param.valType=='bool':
            #only True or False - use a checkbox
             self.valueCtrl = wx.CheckBox(parent, size = wx.Size(self.valueWidth,-1))
             self.valueCtrl.SetValue(param.val)
        elif len(param.allowedVals)>1:
            #there are limited options - use a Choice control
            # use localized text or fall through to non-localized,
            # for future-proofing, parallel-port addresses, etc:
            choiceLabels = []
            for val in param.allowedVals:
                try:
                    choiceLabels.append(_localized[val])
                except KeyError:
                    choiceLabels.append(val)
            self.valueCtrl = wx.Choice(parent, choices=choiceLabels, size=wx.Size(self.valueWidth,-1))
            # stash original non-localized choices:
            self.valueCtrl._choices = copy.copy(param.allowedVals)
            # set display to the localized version of the currently selected value:
            try:
                index = param.allowedVals.index(param.val)
            except:
                logging.warn("%r was given as parameter %r but it isn't in "
                    "the list of allowed values %s. Reverting to use %r for this Component" %(param.val, fieldName, param.allowedVals, param.allowedVals[0]))
                logging.flush()
                index=0
            self.valueCtrl.SetSelection(index)
        else:
            #create the full set of ctrls
            val = unicode(param.val)
            self.valueCtrl = wx.TextCtrl(parent,-1,val,size=wx.Size(self.valueWidth,-1))
            # focus seems to get reset elsewhere, try "git grep -n SetFocus"
            if fieldName in ['allowedKeys', 'image', 'movie', 'scaleDescription', 'sound', 'Begin Routine']:
                self.valueCtrl.SetFocus()
        self.valueCtrl.SetToolTipString(param.hint)
        if len(param.allowedVals)==1 or param.readOnly:
            self.valueCtrl.Disable()#visible but can't be changed

        # add a NameValidator to name valueCtrl
        if fieldName == "name":
            self.valueCtrl.SetValidator(validators.NameValidator())

        #create the type control
        if len(param.allowedTypes):
            # are there any components with non-empty allowedTypes?
            self.typeCtrl = wx.Choice(parent, choices=param.allowedTypes)
            self.typeCtrl._choices = copy.copy(param.allowedTypes)
            index = param.allowedTypes.index(param.valType)
            self.typeCtrl.SetSelection(index)
            if len(param.allowedTypes)==1:
                self.typeCtrl.Disable()#visible but can't be changed

        #create update control
        if param.allowedUpdates is None or len(param.allowedUpdates)==0:
            pass
        else:
            #updates = display-only version of allowed updates
            updateLabels = [_localized[upd] for upd in param.allowedUpdates]
            #allowedUpdates = extend version of allowed updates that includes "set during:static period"
            allowedUpdates = copy.copy(param.allowedUpdates)
            for routineName, routine in self.exp.routines.items():
                for static in routine.getStatics():
                    updateLabels.append(_translate("set during: %(routineName)s.%(staticName)s") % {'routineName':routineName, 'staticName':static.params['name']})
                    allowedUpdates.append("set during: %(routineName)s.%(staticName)s" % {'routineName':routineName, 'staticName':static.params['name']})
            self.updateCtrl = wx.Choice(parent, choices=updateLabels)
            # stash non-localized choices to allow retrieval by index:
            self.updateCtrl._choices = copy.copy(allowedUpdates)
            # get index of the currently set update value, set display:
            index = allowedUpdates.index(param.updates)
            self.updateCtrl.SetSelection(index)  # set by integer index, not string value

        if param.allowedUpdates!=None and len(param.allowedUpdates)==1:
            self.updateCtrl.Disable()#visible but can't be changed
        #create browse control
        if browse:
            self.browseCtrl = wx.Button(parent, -1, _translate("Browse...")) #we don't need a label for this
    def _getCtrlValue(self, ctrl):
        """Retrieve the current value form the control (whatever type of ctrl it
        is, e.g. checkbox.GetValue, choice.GetSelection)
        Different types of control have different methods for retrieving value.
        This function checks them all and returns the value or None.

        .. note::
            Don't use GetStringSelection() here to avoid that translated value
            is returned. Instead, use GetSelection() to get index of selection
            and get untranslated value from _choices attribute.
        """
        if ctrl is None:
            return None
        elif hasattr(ctrl,'GetText'):
            return ctrl.GetText()
        elif hasattr(ctrl, 'GetValue'): #e.g. TextCtrl
            val = ctrl.GetValue()
            if isinstance(self.valueCtrl, dialogs.ListWidget):
                val = self.expInfoFromListWidget(val)
            return val
        elif hasattr(ctrl, 'GetSelection'): #for wx.Choice
            # _choices is defined during __init__ for all wx.Choice() ctrls
            # NOTE: add untranslated value to _choices if _choices[ctrl.GetSelection()] fails.
            return ctrl._choices[ctrl.GetSelection()]
        elif hasattr(ctrl, 'GetLabel'): #for wx.StaticText
            return ctrl.GetLabel()
        else:
            print("failed to retrieve the value for %s" %(ctrl))
            return None
    def _setCtrlValue(self, ctrl, newVal):
        """Set the current value of the control (whatever type of ctrl it
        is, e.g. checkbox.SetValue, choice.SetSelection)
        Different types of control have different methods for retrieving value.
        This function checks them all and returns the value or None.

        .. note::
            Don't use SetStringSelection() here to avoid using translated
            value.  Instead, get index of the value using _choices attribute
            and use SetSelection() to set the value.
        """
        if ctrl is None:
            return None
        elif hasattr(ctrl, 'SetValue'): #e.g. TextCtrl
            ctrl.SetValue(newVal)
        elif hasattr(ctrl, 'SetSelection'): #for wx.Choice
            # _choices = list of non-localized strings, set during __init__
            # NOTE: add untranslated value to _choices if _choices.index(newVal) fails.
            index = ctrl._choices.index(newVal)
            # set the display to the localized version of the string:
            ctrl.SetSelection(index)
        elif hasattr(ctrl, 'SetLabel'): #for wx.StaticText
            ctrl.SetLabel(newVal)
        else:
            print("failed to retrieve the value for %s" %(ctrl))
    def getValue(self):
        """Get the current value of the value ctrl
        """
        return self._getCtrlValue(self.valueCtrl)
    def setValue(self, newVal):
        """Get the current value of the value ctrl
        """
        return self._setCtrlValue(self.valueCtrl, newVal)
    def getType(self):
        """Get the current value of the type ctrl
        """
        if self.typeCtrl:
            return self._getCtrlValue(self.typeCtrl)
    def getUpdates(self):
        """Get the current value of the updates ctrl
        """
        if self.updateCtrl:
            return self._getCtrlValue(self.updateCtrl)
    def setVisible(self, newVal=True):
        self.valueCtrl.Show(newVal)
        self.nameCtrl.Show(newVal)
        if self.updateCtrl:
            self.updateCtrl.Show(newVal)
        if self.typeCtrl:
            self.typeCtrl.Show(newVal)
    def expInfoToListWidget(self, expInfoStr):
        """Takes a string describing a dictionary and turns it into a format
        that the ListWidget can receive (list of dicts of Field:'', Default:'')
        """
        expInfo = eval(expInfoStr)
        listOfDicts = []
        for field, default in expInfo.items():
            listOfDicts.append({'Field':field, 'Default':default})
        return listOfDicts
    def expInfoFromListWidget(self, listOfDicts):
        """Creates a string representation of a dict from a list of field/default
        values.
        """
        expInfo = {}
        for field in listOfDicts:
            expInfo[field['Field']] = field['Default']
        expInfoStr = repr(expInfo)
        return expInfoStr


class _BaseParamsDlg(wx.Dialog):
    def __init__(self,frame,title,params,order,
            helpUrl=None, suppressTitles=True,
            showAdvanced=False,
            size=wx.DefaultSize,
            style=wx.DEFAULT_DIALOG_STYLE|wx.DIALOG_NO_PARENT|wx.TAB_TRAVERSAL,editing=False):

        # translate title
        if ' Properties' in title: # Components and Loops
            localizedTitle = title.replace(' Properties',_translate(' Properties'))
        else:
            localizedTitle = _translate(title)

        wx.Dialog.__init__(self, frame,-1,localizedTitle,size=size,style=style) #use translated title for display
        self.frame=frame
        self.app=frame.app
        self.dpi=self.app.dpi
        self.helpUrl=helpUrl
        self.params=params   #dict
        self.title = title
        if not editing and title != 'Experiment Settings' and 'name' in self.params.keys():
            # then we're adding a new component, so provide a known-valid name:
            self.params['name'].val = self.frame.exp.namespace.makeValid(params['name'].val)
        self.paramCtrls={}
        self.suppressTitles = suppressTitles
        self.showAdvanced=showAdvanced
        self.order=order
        self.data = []
        self.nameOKlabel=None
        self.maxFieldLength = 10#max( len(str(self.params[x])) for x in keys )
        self.timeParams=['startType','startVal','stopType','stopVal']
        self.codeFieldNameFromID = {}
        self.codeIDFromFieldName = {}
        self.panels = []# a list of all panels in the ctrl to be traversed by validator

        # for switching font to signal code:
        self.codeFaceName = 'Courier New'  # get another monospace if not available
        # need font size for STCs:
        if wx.Platform == '__WXMSW__':
            self.faceSize = 10
        elif wx.Platform == '__WXMAC__':
            self.faceSize = 14
        else:
            self.faceSize = 12

        #organise the param names by category
        categs = {'Basic':[]}
        for thisName in sorted(self.params):
            thisParam = self.params[thisName]
            if type(thisParam)==list:
                continue#not really a param as such
            thisCateg = thisParam.categ
            if thisCateg not in categs:
                categs[thisCateg] = [thisName]
            else:
                categs[thisCateg].append(thisName)
        if not categs['Basic']: #there were no entries of this categ so delete it
            del categs['Basic']

        #create main sizer
        self.mainSizer=wx.BoxSizer(wx.VERTICAL)
        agwStyle = flatnotebook.FNB_NO_X_BUTTON
        if hasattr(flatnotebook, "FNB_NAV_BUTTONS_WHEN_NEEDED"):
            # not available in wxPython 2.8
            agwStyle |= flatnotebook.FNB_NAV_BUTTONS_WHEN_NEEDED
        if hasattr(flatnotebook, "FNB_NO_TAB_FOCUS"):
            # not available in wxPython 2.8.10
            agwStyle |= flatnotebook.FNB_NO_TAB_FOCUS
        self.ctrls = flatnotebook.FlatNotebook(self, style = agwStyle)
        self.mainSizer.Add(self.ctrls, flag=wx.EXPAND|wx.ALL)#add main controls
        categNames = sorted(categs)
        if 'Basic' in categNames:
            #move it to be the first category we see
            categNames.insert(0, categNames.pop(categNames.index('Basic')))
        # move into _localized after merge branches:
        categLabel = {'Basic': _translate('Basic'), 'Data': _translate('Data'), 'Screen': _translate('Screen'),
                      'Dots': _translate('Dots'), 'Grating': _translate('Grating'),
                      'Advanced': _translate('Advanced'), 'Custom': _translate('Custom')}
        for categName in categNames:
            theseParams = categs[categName]
            page = wx.Panel(self.ctrls, -1)
            ctrls = self.addCategoryOfParams(theseParams, parent=page)
            page.SetSizer(ctrls)
            if categName in categLabel.keys():
                cat = categLabel[categName]
            else:
                cat = categName
            self.ctrls.AddPage(page, cat)
            self.panels.append(page) #so the validator finds this set of controls
            if 'customize_everything' in self.params.keys():
                if self.params['customize_everything'].val.strip():
                    # set focus to the custom panel, because custom will trump others
                    page.SetFocus()
                    self.ctrls.SetSelection(self.ctrls.GetPageCount()-1)
            else:
                self.ctrls.GetPage(0).SetFocus()
                self.ctrls.SetSelection(0)
                if hasattr(self, 'paramCtrls'):
                    if 'name' in self.paramCtrls:
                        self.paramCtrls['name'].valueCtrl.SetFocus()
                    if 'expName' in self.paramCtrls:# ExperimentSettings has expName instead
                        self.paramCtrls['expName'].valueCtrl.SetFocus()
    def addCategoryOfParams(self, paramNames, parent):
        """Add all the params for a single category (after its tab has been created)
        """
        #create the sizers to fit the params and set row to zero
        sizer= wx.GridBagSizer(vgap=2,hgap=2)
        sizer.AddGrowableCol(0)#valueCtrl column
        currRow = 0
        self.useUpdates=False#does the dlg need an 'updates' row (do any params use it?)

        #create a header row of titles
        if not self.suppressTitles:
            size=wx.Size(1.5*self.dpi,-1)
            sizer.Add(wx.StaticText(parent,-1,'Parameter',size=size, style=wx.ALIGN_CENTER),(currRow,0))
            sizer.Add(wx.StaticText(parent,-1,'Value',size=size, style=wx.ALIGN_CENTER),(currRow,1))
            #self.sizer.Add(wx.StaticText(self,-1,'Value Type',size=size, style=wx.ALIGN_CENTER),(currRow,3))
            sizer.Add(wx.StaticText(parent,-1,'Updates',size=size, style=wx.ALIGN_CENTER),(currRow,2))
            currRow+=1
            sizer.Add(
                wx.StaticLine(parent, size=wx.Size(100,20)),
                (currRow,0),(1,2), wx.ALIGN_CENTER|wx.EXPAND)
        currRow+=1

        #get all params and sort
        remaining = copy.copy(paramNames)

        #start with the name (always)
        if 'name' in remaining:
            self.addParam('name', parent, sizer, currRow)
            currRow += 1
            remaining.remove('name')
            if 'name' in self.order:
                self.order.remove('name')
            currRow+=1
        #add start/stop info
        if 'startType' in remaining:
            remaining, currRow = self.addStartStopCtrls(remaining, parent, sizer, currRow)
        currRow += 1
        #loop through the prescribed order (the most important?)
        for fieldName in self.order:
            if fieldName not in paramNames:
                continue#skip advanced params
            self.addParam(fieldName, parent, sizer, currRow, valType=self.params[fieldName].valType)
            currRow += 1
            remaining.remove(fieldName)
        #add any params that weren't specified in the order
        for fieldName in remaining:
            self.addParam(fieldName, parent, sizer, currRow, valType=self.params[fieldName].valType)
            currRow += 1
        return sizer

    def addStartStopCtrls(self,remaining, parent, sizer, currRow):
        """Add controls for startType, startVal, stopType, stopVal
        remaining refers to
        """
        ##Start point
        startTypeParam = self.params['startType']
        startValParam = self.params['startVal']
        #create label
        label = wx.StaticText(parent,-1,_translate('Start'), style=wx.ALIGN_CENTER)
        labelEstim = wx.StaticText(parent,-1,_translate('Expected start (s)'), style=wx.ALIGN_CENTER)
        labelEstim.SetForegroundColour('gray')
        #the method to be used to interpret this start/stop
        self.startTypeCtrl = wx.Choice(parent, choices=map(_translate,startTypeParam.allowedVals))
        self.startTypeCtrl.SetStringSelection(_translate(startTypeParam.val))
        self.startTypeCtrl.SetToolTipString(self.params['startType'].hint)
        #the value to be used as the start/stop
        self.startValCtrl = wx.TextCtrl(parent,-1,unicode(startValParam.val))
        self.startValCtrl.SetToolTipString(self.params['startVal'].hint)
        #the value to estimate start/stop if not numeric
        self.startEstimCtrl = wx.TextCtrl(parent,-1,unicode(self.params['startEstim'].val))
        self.startEstimCtrl.SetToolTipString(self.params['startEstim'].hint)
        #add the controls to a new line
        startSizer = wx.BoxSizer(orient=wx.HORIZONTAL)
        startSizer.Add(self.startTypeCtrl)
        startSizer.Add(self.startValCtrl, 1,flag=wx.EXPAND)
        startEstimSizer=wx.BoxSizer(orient=wx.HORIZONTAL)
        startEstimSizer.Add(labelEstim, flag = wx.ALIGN_CENTRE_VERTICAL|wx.ALIGN_LEFT)
        startEstimSizer.Add(self.startEstimCtrl, flag = wx.ALIGN_BOTTOM)
        startAllCrtlSizer = wx.BoxSizer(orient=wx.VERTICAL)
        startAllCrtlSizer.Add(startSizer,flag=wx.EXPAND)
        startAllCrtlSizer.Add(startEstimSizer, flag=wx.ALIGN_RIGHT)
        sizer.Add(label, (currRow,0),(1,1),wx.ALIGN_RIGHT)
        #add our new row
        sizer.Add(startAllCrtlSizer,(currRow,1),(1,1),flag=wx.EXPAND)
        currRow+=1
        remaining.remove('startType')
        remaining.remove('startVal')
        remaining.remove('startEstim')

        ##Stop point
        stopTypeParam = self.params['stopType']
        stopValParam = self.params['stopVal']
        #create label
        label = wx.StaticText(parent,-1,_translate('Stop'), style=wx.ALIGN_CENTER)
        labelEstim = wx.StaticText(parent,-1,_translate('Expected duration (s)'), style=wx.ALIGN_CENTER)
        labelEstim.SetForegroundColour('gray')
        #the method to be used to interpret this start/stop
        self.stopTypeCtrl = wx.Choice(parent, choices=map(_translate,stopTypeParam.allowedVals))
        self.stopTypeCtrl.SetStringSelection(_translate(stopTypeParam.val))
        self.stopTypeCtrl.SetToolTipString(self.params['stopType'].hint)
        #the value to be used as the start/stop
        self.stopValCtrl = wx.TextCtrl(parent,-1,unicode(stopValParam.val))
        self.stopValCtrl.SetToolTipString(self.params['stopVal'].hint)
        #the value to estimate start/stop if not numeric
        self.durationEstimCtrl = wx.TextCtrl(parent,-1,unicode(self.params['durationEstim'].val))
        self.durationEstimCtrl.SetToolTipString(self.params['durationEstim'].hint)
        #add the controls to a new line
        stopSizer = wx.BoxSizer(orient=wx.HORIZONTAL)
        stopSizer.Add(self.stopTypeCtrl)
        stopSizer.Add(self.stopValCtrl, 1,flag=wx.EXPAND)
        stopEstimSizer=wx.BoxSizer(orient=wx.HORIZONTAL)
        stopEstimSizer.Add(labelEstim, flag = wx.ALIGN_CENTRE_VERTICAL)
        stopEstimSizer.Add(self.durationEstimCtrl, flag = wx.ALIGN_CENTRE_VERTICAL)
        stopAllCrtlSizer = wx.BoxSizer(orient=wx.VERTICAL)
        stopAllCrtlSizer.Add(stopSizer,flag=wx.EXPAND)
        stopAllCrtlSizer.Add(stopEstimSizer, flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTRE_VERTICAL)
        sizer.Add(label, (currRow,0),(1,1),wx.ALIGN_RIGHT)
        #add our new row
        sizer.Add(stopAllCrtlSizer,(currRow,1),(1,1),flag=wx.EXPAND)
        currRow+=1
        remaining.remove('stopType')
        remaining.remove('stopVal')
        remaining.remove('durationEstim')

        # use monospace font to signal code:
        self.checkCodeWanted(self.startValCtrl)
        self.startValCtrl.Bind(wx.EVT_KEY_UP, self.checkCodeWanted)
        self.checkCodeWanted(self.stopValCtrl)
        self.stopValCtrl.Bind(wx.EVT_KEY_UP, self.checkCodeWanted)

        return remaining, currRow

    def addParam(self,fieldName, parent, sizer, currRow, advanced=False, valType=None):
        """Add a parameter to the basic sizer
        """
        param=self.params[fieldName]
        if param.label not in [None, '']:
            label=param.label
        else:
            label=fieldName
        ctrls=ParamCtrls(dlg=self, parent=parent, label=label, fieldName=fieldName,
                         param=param, advanced=advanced, appPrefs=self.app.prefs)
        self.paramCtrls[fieldName] = ctrls
        if fieldName=='name':
            ctrls.valueCtrl.Bind(wx.EVT_TEXT, self.checkName)
            ctrls.valueCtrl.SetFocus()
        # self.valueCtrl = self.typeCtrl = self.updateCtrl
        sizer.Add(ctrls.nameCtrl, (currRow,0), border=5,
            flag=wx.ALIGN_RIGHT|wx.ALIGN_CENTRE_VERTICAL|wx.LEFT|wx.RIGHT)
        sizer.Add(ctrls.valueCtrl, (currRow,1), border=5,
            flag=wx.EXPAND | wx.ALIGN_CENTRE_VERTICAL | wx.ALL)
        if ctrls.updateCtrl:
            sizer.Add(ctrls.updateCtrl, (currRow,2))
        if ctrls.typeCtrl:
            sizer.Add(ctrls.typeCtrl, (currRow,3) )
        if fieldName in ['text']:
            sizer.AddGrowableRow(currRow)#doesn't seem to work though
            #self.Bind(EVT_ETC_LAYOUT_NEEDED, self.onNewTextSize, ctrls.valueCtrl)
        elif fieldName in ['color', 'fillColor', 'lineColor']:
            ctrls.valueCtrl.Bind(wx.EVT_RIGHT_DOWN, self.launchColorPicker)
        elif valType == 'extendedCode':
            sizer.AddGrowableRow(currRow)#doesn't seem to work though
            ctrls.valueCtrl.Bind(wx.EVT_KEY_DOWN, self.onTextEventCode)
        elif fieldName=='Monitor':
            ctrls.valueCtrl.Bind(wx.EVT_RIGHT_DOWN, self.openMonitorCenter)

        # use monospace font to signal code:
        if fieldName != 'name' and hasattr(ctrls.valueCtrl, 'GetFont'):
            if self.params[fieldName].valType == 'code':
                ctrls.valueCtrl.SetFont(self.app._codeFont)
            elif self.params[fieldName].valType == 'str':
                ctrls.valueCtrl.Bind(wx.EVT_KEY_UP, self.checkCodeWanted)
                try:
                    self.checkCodeWanted(ctrls.valueCtrl)
                except:
                    pass

    def openMonitorCenter(self,event):
        self.app.openMonitorCenter(event)
        self.paramCtrls['Monitor'].valueCtrl.SetFocus()
        # need to delay until the user closes the monitor center
        #self.paramCtrls['Monitor'].valueCtrl.Clear()
        #if wx.TheClipboard.Open():
        #    dataObject = wx.TextDataObject()
        #    if wx.TheClipboard.GetData(dataObject):
        #        self.paramCtrls['Monitor'].valueCtrl.WriteText(dataObject.GetText())
        #    wx.TheClipboard.Close()
    def launchColorPicker(self, event):
        # bring up a colorPicker
        rgb = self.app.colorPicker(None) # str, remapped to -1..+1
        self.paramCtrls['color'].valueCtrl.SetFocus()
        self.paramCtrls['color'].valueCtrl.Clear()
        self.paramCtrls['color'].valueCtrl.WriteText('$'+rgb) # $ flag as code
        ii = self.paramCtrls['colorSpace'].valueCtrl.FindString('rgb')
        self.paramCtrls['colorSpace'].valueCtrl.SetSelection(ii)

    def onNewTextSize(self, event):
        self.Fit()#for ExpandoTextCtrl this is needed

    def show(self):
        """Adds an OK and cancel button, shows dialogue.

        This method returns wx.ID_OK (as from ShowModal), but also
        sets self.OK to be True or False
        """
        #add a label to check name
        if 'name' in self.params.keys():
            #if len(self.params['name'].val):
            #    nameInfo=''
            #else:
            #    nameInfo='Need a name'
            nameInfo = ''
            self.nameOKlabel=wx.StaticText(self,-1,nameInfo,size=(300,25),
                                        style=wx.ALIGN_CENTRE)
            self.nameOKlabel.SetForegroundColour(wx.RED)
            self.mainSizer.Add(self.nameOKlabel, wx.ALIGN_CENTRE|wx.EXPAND)
        #add buttons for OK and Cancel
        buttons = wx.StdDialogButtonSizer()
        #help button if we know the url
        if self.helpUrl!=None:
            helpBtn = wx.Button(self, wx.ID_HELP, _translate(" Help "))
            helpBtn.SetToolTip(wx.ToolTip(_translate("Go to online help about this component")))
            helpBtn.Bind(wx.EVT_BUTTON, self.onHelp)
            buttons.Add(helpBtn, 0, wx.ALIGN_LEFT|wx.ALL,border=3)
            buttons.AddSpacer(12)
        self.OKbtn = wx.Button(self, wx.ID_OK, _translate(" OK "))
        # intercept OK button if a loop dialog, in case file name was edited:
        if type(self) == DlgLoopProperties:
            self.OKbtn.Bind(wx.EVT_BUTTON, self.onOK)
        self.OKbtn.SetDefault()

        self.checkName() # disables OKbtn if bad name
        buttons.Add(self.OKbtn, 0, wx.ALL,border=3)
        CANCEL = wx.Button(self, wx.ID_CANCEL, _translate(" Cancel "))
        buttons.Add(CANCEL, 0, wx.ALL,border=3)
        buttons.Realize()
        #add to sizer
        self.mainSizer.Add(buttons, flag=wx.ALIGN_RIGHT)
        border = wx.BoxSizer(wx.VERTICAL)
        border.Add(self.mainSizer, flag=wx.ALL|wx.EXPAND, border=8)
        self.SetSizerAndFit(border)
        #move the position to be v near the top of screen and to the right of the left-most edge of builder
        builderPos = self.frame.GetPosition()
        self.SetPosition((builderPos[0]+200,20))

        #self.paramCtrls['name'].valueCtrl.SetFocus()
        #do show and process return
        retVal = self.ShowModal()
        if retVal== wx.ID_OK:
            self.OK=True
        else:
            self.OK=False
        return wx.ID_OK

    def Validate(self, *args, **kwargs):
        """
        Validate form data and disable OK button if validation fails.
        """
        valid = super(_BaseParamsDlg, self).Validate(*args, **kwargs)
        #also validate each page in the ctrls notebook
        for thisPanel in self.panels:
            stillValid = thisPanel.Validate()
            valid = valid and stillValid
        if valid:
            self.OKbtn.Enable()
        else:
            self.OKbtn.Disable()
        return valid

    def onOK(self, event=None):
        """
        Handler for OK button which should validate dialog contents.
        """
        valid = self.Validate()
        if not valid:
            return
        event.Skip()

    def onTextEventCode(self, event=None):
        """process text events for code components: change color to grey
        """
        codeBox = event.GetEventObject()
        textBeforeThisKey = codeBox.GetText()
        keyCode = event.GetKeyCode()
        pos = event.GetPosition()
        if keyCode<256 and keyCode not in [10,13]: # ord(10)='\n', ord(13)='\l'
            #new line is trigger to check syntax
            codeBox.setStatus('changed')
        elif keyCode in [10,13] and len(textBeforeThisKey) and textBeforeThisKey[-1] != ':':
            # ... but skip the check if end of line is colon ord(58)=':'
            self._setNameColor(self._testCompile(codeBox))
        event.Skip()
    def _testCompile(self, ctrl, mode='exec'):
        """checks whether code.val is legal python syntax, returns error status

        mode = 'exec' (statement or expr) or 'eval' (expr only)
        """
        if hasattr(ctrl,'GetText'):
            val = ctrl.GetText()
        elif hasattr(ctrl, 'GetValue'):  #e.g. TextCtrl
            val = ctrl.GetValue()
        else:
            raise ValueError('Unknown type of ctrl in _testCompile: %s' %(type(ctrl)))
        try:
            compile(val, '', mode)
            syntaxOk = True
            ctrl.setStatus('OK')
        except SyntaxError:
            ctrl.setStatus('error')
            syntaxOk = False
        return syntaxOk

    def checkCodeSyntax(self, event=None):
        """Checks syntax for whole code component by code box, sets box bg-color.
        """
        if hasattr(event, 'GetEventObject'):
            codeBox = event.GetEventObject()
        elif hasattr(event,'GetText'):
            codeBox = event #we were given the control itself, not an event
        else:
            raise ValueError('checkCodeSyntax received unexpected event object (%s). Should be a wx.Event or a CodeBox' %type(event))
        text = codeBox.GetText()
        if not text.strip(): # if basically empty
            codeBox.SetBackgroundColour(white)
            return # skip test
        goodSyntax = self._testCompile(codeBox) # test syntax
        #not quite every dialog has a name (e.g. settings) but if so then set its color
        if 'name' in self.paramCtrls:
            self._setNameColor(goodSyntax)
    def _setNameColor(self, goodSyntax):
        if goodSyntax:
            self.paramCtrls['name'].valueCtrl.SetBackgroundColour(codeSyntaxOkay)
            self.nameOKlabel.SetLabel("")
        else:
            self.paramCtrls['name'].valueCtrl.SetBackgroundColour(white)
            self.nameOKlabel.SetLabel('syntax error')

    def checkCodeWanted(self, event=None):
        """check whether a $ is present (if so, set the display font)
        """
        if hasattr(event, 'GetEventObject'):
            strBox = event.GetEventObject()
        elif hasattr(event, 'GetValue'):
            strBox = event  # we were given the control itself, not an event
        else:
            raise ValueError('checkCodeWanted received unexpected event object (%s).')
        try:
            val = strBox.GetValue()
            stc = False
        except:
            if not hasattr(strBox, 'GetText'):  # eg, wx.Choice control
                if hasattr(event, 'Skip'):
                    event.Skip()
                return
            val = strBox.GetText()
            stc = True  # might be StyledTextCtrl

        # set display font based on presence of $ (without \$)?
        font = strBox.GetFont()
        if _unescapedDollarSign_re.search(val):
            strBox.SetFont(self.app._codeFont)
        else:
            strBox.SetFont(self.app._mainFont)

        if hasattr(event, 'Skip'):
            event.Skip()

    def getParams(self):
        """retrieves data from any fields in self.paramCtrls
        (populated during the __init__ function)

        The new data from the dlg get inserted back into the original params
        used in __init__ and are also returned from this method.
        """
        #get data from input fields
        for fieldName in self.params.keys():
            param=self.params[fieldName]
            if fieldName=='advancedParams':
                pass
            elif fieldName=='startType':
                param.val = self.params['startType'].allowedVals[self.startTypeCtrl.GetCurrentSelection()]
            elif fieldName=='stopType':
                param.val = self.params['stopType'].allowedVals[self.stopTypeCtrl.GetCurrentSelection()]
            elif fieldName=='startVal':
                param.val = self.startValCtrl.GetValue()
            elif fieldName=='stopVal':
                param.val = self.stopValCtrl.GetValue()
            elif fieldName=='startEstim':
                param.val = self.startEstimCtrl.GetValue()
            elif fieldName=='durationEstim':
                param.val = self.durationEstimCtrl.GetValue()
            else:
                ctrls = self.paramCtrls[fieldName]#the various dlg ctrls for this param
                param.val = ctrls.getValue()
                if ctrls.typeCtrl:
                    param.valType = ctrls.getType()
                if ctrls.updateCtrl:
                    #may also need to update a static
                    updates = ctrls.getUpdates()
                    if param.updates != updates:
                        self._updateStaticUpdates(fieldName, param.updates, updates)
                        param.updates=updates
        return self.params
    def _updateStaticUpdates(self, fieldName, updates, newUpdates):
        """If the old/new updates ctrl is using a Static component then we
        need to remove/add the component name to the appropriate static
        """
        exp = self.frame.exp
        compName = self.params['name'].val
        if hasattr(updates, 'startswith') and "during:" in updates:
            updates = updates.split(': ')[1] #remove the part that says 'during'
            origRoutine, origStatic =  updates.split('.')
            if exp.routines[origRoutine].getComponentFromName(origStatic) != None:
                exp.routines[origRoutine].getComponentFromName(origStatic).remComponentUpdate(
                    origRoutine, compName, fieldName)
        if hasattr(newUpdates, 'startswith') and "during:" in newUpdates:
            newUpdates = newUpdates.split(': ')[1] #remove the part that says 'during'
            newRoutine, newStatic =  newUpdates.split('.')
            exp.routines[newRoutine].getComponentFromName(newStatic).addComponentUpdate(
                newRoutine, compName, fieldName)
    def _checkName(self, event=None, name=None):
        """checks namespace, return error-msg (str), enable (bool)
        """
        if event:
            newName = event.GetString()
        elif name:
            newName = name
        elif hasattr(self, 'paramCtrls'):
            newName=self.paramCtrls['name'].getValue()
        elif hasattr(self, 'globalCtrls'):
            newName=self.globalCtrls['name'].getValue()
        if newName=='':
            return _translate("Missing name"), False
        else:
            namespace = self.frame.exp.namespace
            used = namespace.exists(newName)
            same_as_old_name = bool(newName == self.params['name'].val)
            if used and not same_as_old_name:
                return _translate("That name is in use (it's a %s). Try another name.") % namespace._localized[used], False
            elif not namespace.isValid(newName): # valid as a var name
                return _translate("Name must be alpha-numeric or _, no spaces"), False
            elif namespace.isPossiblyDerivable(newName): # warn but allow, chances are good that its actually ok
                msg = namespace.isPossiblyDerivable(newName)
                return namespace._localized[msg], True
            else:
                return "", True
    def checkName(self, event=None):
        """
        Issue a form validation on name change.
        """
        self.Validate()

    def onHelp(self, event=None):
        """Uses self.app.followLink() to self.helpUrl
        """
        self.app.followLink(url=self.helpUrl)


class DlgLoopProperties(_BaseParamsDlg):
    def __init__(self,frame,title="Loop Properties",loop=None,
            helpUrl=None,
            pos=wx.DefaultPosition, size=wx.DefaultSize,
            style=wx.DEFAULT_DIALOG_STYLE|wx.DIALOG_NO_PARENT|wx.RESIZE_BORDER):
        # translate title
        localizedTitle = title.replace(' Properties',_translate(' Properties'))

        wx.Dialog.__init__(self, frame,-1,localizedTitle,pos,size,style) # use localized title
        self.helpUrl=helpUrl
        self.frame=frame
        self.exp=frame.exp
        self.app=frame.app
        self.dpi=self.app.dpi
        self.params={}
        self.panel = wx.Panel(self, -1)
        self.globalCtrls={}
        self.constantsCtrls={}
        self.staircaseCtrls={}
        self.multiStairCtrls={}
        self.currentCtrls={}
        self.data = []
        self.mainSizer= wx.BoxSizer(wx.VERTICAL)
        self.conditions=None
        self.conditionsFile=None
        #create a valid new name; save old name in case we need to revert
        defaultName = 'trials'
        oldLoopName = defaultName
        if loop:
            oldLoopName = loop.params['name'].val
        namespace = frame.exp.namespace
        new_name = namespace.makeValid(oldLoopName)
        #create default instances of the diff loop types
        self.trialHandler=experiment.TrialHandler(exp=self.exp, name=new_name,
            loopType='random',nReps=5,conditions=[]) #for 'random','sequential', 'fullRandom'
        self.stairHandler=experiment.StairHandler(exp=self.exp, name=new_name,
            nReps=50, nReversals='',
            stepSizes='[0.8,0.8,0.4,0.4,0.2]', stepType='log', startVal=0.5) #for staircases
        self.multiStairHandler=experiment.MultiStairHandler(exp=self.exp, name=new_name,
            nReps=50, stairType='simple', switchStairs='random',
            conditions=[], conditionsFile='')
        #replace defaults with the loop we were given
        if loop is None:
            self.currentType='random'
            self.currentHandler=self.trialHandler
        elif loop.type=='TrialHandler':
            self.conditions=loop.params['conditions'].val
            self.conditionsFile=loop.params['conditionsFile'].val
            self.trialHandler = self.currentHandler = loop
            self.currentType=loop.params['loopType'].val #could be 'random', 'sequential', 'fullRandom'
        elif loop.type=='StairHandler':
            self.stairHandler = self.currentHandler = loop
            self.currentType='staircase'
        elif loop.type=='MultiStairHandler':
            self.conditions=loop.params['conditions'].val
            self.conditionsFile=loop.params['conditionsFile'].val
            self.multiStairHandler = self.currentHandler = loop
            self.currentType='interleaved staircases'
        elif loop.type=='QuestHandler':
            pass # what to do for quest?
        self.params['name']=self.currentHandler.params['name']
        self.globalPanel = self.makeGlobalCtrls()
        self.stairPanel = self.makeStaircaseCtrls()
        self.constantsPanel = self.makeConstantsCtrls()#the controls for Method of Constants
        self.multiStairPanel = self.makeMultiStairCtrls()
        self.mainSizer.Add(self.globalPanel, border=5, flag=wx.ALL|wx.ALIGN_CENTRE)
        self.mainSizer.Add(wx.StaticLine(self), border=5, flag=wx.ALL|wx.EXPAND)
        self.mainSizer.Add(self.stairPanel, border=5, flag=wx.ALL|wx.ALIGN_CENTRE)
        self.mainSizer.Add(self.constantsPanel, border=5, flag=wx.ALL|wx.ALIGN_CENTRE)
        self.mainSizer.Add(self.multiStairPanel, border=5, flag=wx.ALL|wx.ALIGN_CENTRE)
        self.setCtrls(self.currentType)
        # create a list of panels in the dialog, for the validator to step through
        self.panels = [self.globalPanel, self.stairPanel, self.constantsPanel, self.multiStairPanel]


        #show dialog and get most of the data
        self.show()
        if self.OK:
            self.params = self.getParams()
            #convert endPoints from str to list
            exec("self.params['endPoints'].val = %s" %self.params['endPoints'].val)
            #then sort the list so the endpoints are in correct order
            self.params['endPoints'].val.sort()
            if loop: # editing an existing loop
                namespace.remove(oldLoopName)
            namespace.add(self.params['name'].val)
            # don't always have a conditionsFile
            if hasattr(self, 'condNamesInFile'):
                namespace.add(self.condNamesInFile)
            if hasattr(self, 'duplCondNames'):
                namespace.remove(self.duplCondNames)
        else:
            if loop!=None:#if we had a loop during init then revert to its old name
                loop.params['name'].val = oldLoopName

        #make sure we set this back regardless of whether OK
        #otherwise it will be left as a summary string, not a conditions
        if 'conditionsFile' in self.currentHandler.params:
            self.currentHandler.params['conditions'].val=self.conditions

    def makeGlobalCtrls(self):
        panel = wx.Panel(parent=self)
        panelSizer = wx.GridBagSizer(5,5)
        panel.SetSizer(panelSizer)
        row=0
        for fieldName in ['name','loopType','isTrials']:
            try:
                label = self.currentHandler.params[fieldName].label
            except:
                label = fieldName
            self.globalCtrls[fieldName] = ctrls = ParamCtrls(dlg=self, parent=panel,
                label=label,fieldName=fieldName,
                param=self.currentHandler.params[fieldName])
            panelSizer.Add(ctrls.nameCtrl, [row, 0], border=1,
                flag=wx.EXPAND | wx.ALIGN_CENTRE_VERTICAL | wx.ALL)
            panelSizer.Add(ctrls.valueCtrl, [row, 1], border=1,
                flag=wx.EXPAND | wx.ALIGN_CENTRE_VERTICAL | wx.ALL)
            row += 1

        self.globalCtrls['name'].valueCtrl.Bind(wx.EVT_TEXT, self.checkName)
        self.Bind(wx.EVT_CHOICE, self.onTypeChanged, self.globalCtrls['loopType'].valueCtrl)
        return panel

    def makeConstantsCtrls(self):
        #a list of controls for the random/sequential versions
        #that can be hidden or shown
        handler=self.trialHandler
        #loop through the params
        keys = handler.params.keys()
        panel = wx.Panel(parent=self)
        panelSizer = wx.GridBagSizer(5,5)
        panel.SetSizer(panelSizer)
        row=0
        #add conditions stuff to the *end*
        if 'conditionsFile' in keys:
            keys.remove('conditionsFile')
            keys.append('conditionsFile')
        if 'conditions' in keys:
            keys.remove('conditions')
            keys.append('conditions')
        #then step through them
        for fieldName in keys:
            #try and get alternative "label" for the parameter
            try:
                label = self.currentHandler.params[fieldName].label
                if not label: #it might exist but be empty
                    label = fieldName
            except:
                label = fieldName
            #handle special cases
            if fieldName=='endPoints':
                continue#this was deprecated in v1.62.00
            if fieldName in self.globalCtrls:
                #these have already been made and inserted into sizer
                ctrls=self.globalCtrls[fieldName]
            elif fieldName=='conditionsFile':
                ctrls=ParamCtrls(dlg=self, parent=panel, label=label,fieldName=fieldName,
                    param=handler.params[fieldName], browse=True)
                self.Bind(wx.EVT_BUTTON, self.onBrowseTrialsFile,ctrls.browseCtrl)
                ctrls.valueCtrl.Bind(wx.EVT_RIGHT_DOWN, self.viewConditions)
                panelSizer.Add(ctrls.nameCtrl, [row, 0])
                panelSizer.Add(ctrls.valueCtrl, [row, 1])
                panelSizer.Add(ctrls.browseCtrl, [row, 2])
                row += 1
            elif fieldName=='conditions':
                if 'conditions' in handler.params:
                    text=self.getTrialsSummary(handler.params['conditions'].val)
                else:
                    text = _translate("No parameters set")
                ctrls = ParamCtrls(dlg=self, parent=panel, label=label, fieldName=fieldName,
                    param=text, noCtrls=True)#we'll create our own widgets
                size = wx.Size(350, 50)
                ctrls.valueCtrl = wx.StaticText(panel, label=text, size=size, style=wx.ALIGN_CENTER)
                panelSizer.Add(ctrls.valueCtrl, (row, 0), span=(1,3), flag=wx.ALIGN_CENTER)
                row += 1
            else: #normal text entry field
                ctrls=ParamCtrls(dlg=self, parent=panel, label=label,fieldName=fieldName,
                    param=handler.params[fieldName])
                panelSizer.Add(ctrls.nameCtrl, [row, 0])
                panelSizer.Add(ctrls.valueCtrl, [row, 1])
                row += 1
            #store info about the field
            self.constantsCtrls[fieldName] = ctrls
        return panel

    def makeMultiStairCtrls(self):
        #a list of controls for the random/sequential versions
        panel = wx.Panel(parent=self)
        panelSizer = wx.GridBagSizer(5,5)
        panel.SetSizer(panelSizer)
        row=0
        #that can be hidden or shown
        handler=self.multiStairHandler
        #loop through the params
        keys = handler.params.keys()
        #add conditions stuff to the *end*
        #add conditions stuff to the *end*
        if 'conditionsFile' in keys:
            keys.remove('conditionsFile')
            keys.append('conditionsFile')
        if 'conditions' in keys:
            keys.remove('conditions')
            keys.append('conditions')
        #then step through them
        for fieldName in keys:
            #try and get alternative "label" for the parameter
            try:
                label = handler.params[fieldName].label
                if not label: #it might exist but be empty
                    label = fieldName
            except:
                label = fieldName
            #handle special cases
            if fieldName=='endPoints':
                continue  #this was deprecated in v1.62.00
            if fieldName in self.globalCtrls:
                #these have already been made and inserted into sizer
                ctrls=self.globalCtrls[fieldName]
            elif fieldName=='conditionsFile':
                ctrls=ParamCtrls(dlg=self, parent=panel, label=label, fieldName=fieldName,
                    param=handler.params[fieldName], browse=True)
                self.Bind(wx.EVT_BUTTON, self.onBrowseTrialsFile,ctrls.browseCtrl)
                panelSizer.Add(ctrls.nameCtrl, [row, 0])
                panelSizer.Add(ctrls.valueCtrl, [row, 1])
                panelSizer.Add(ctrls.browseCtrl, [row, 2])
                row += 1
            elif fieldName=='conditions':
                if 'conditions' in handler.params:
                    text=self.getTrialsSummary(handler.params['conditions'].val)
                else:
                    text = _translate("No parameters set (select a file above)")
                ctrls = ParamCtrls(dlg=self, parent=panel, label=label, fieldName=fieldName,
                    param=text, noCtrls=True)#we'll create our own widgets
                size = wx.Size(350, 50)
                ctrls.valueCtrl = wx.StaticText(panel, label=text, size=size, style=wx.ALIGN_CENTER)
                panelSizer.Add(ctrls.valueCtrl, (row, 0), span=(1,3), flag=wx.ALIGN_CENTER)
                row += 1
            else: #normal text entry field
                ctrls=ParamCtrls(dlg=self, parent=panel, label=label, fieldName=fieldName,
                    param=handler.params[fieldName])
                panelSizer.Add(ctrls.nameCtrl, [row, 0])
                panelSizer.Add(ctrls.valueCtrl, [row, 1])
                row += 1
            #store info about the field
            self.multiStairCtrls[fieldName] = ctrls
        return panel

    def makeStaircaseCtrls(self):
        """Setup the controls for a StairHandler"""
        panel = wx.Panel(parent=self)
        panelSizer = wx.GridBagSizer(5,5)
        panel.SetSizer(panelSizer)
        row=0
        handler=self.stairHandler
        #loop through the params
        for fieldName in handler.params:
            #try and get alternative "label" for the parameter
            try:
                label = handler.params[fieldName].label
                if not label: #it might exist but be empty
                    label = fieldName
            except:
                label = fieldName
            #handle special cases
            if fieldName=='endPoints':
                continue#this was deprecated in v1.62.00
            if fieldName in self.globalCtrls:
                #these have already been made and inserted into sizer
                ctrls=self.globalCtrls[fieldName]
            else: #normal text entry field
                ctrls=ParamCtrls(dlg=self, parent=panel, label=label, fieldName=fieldName,
                    param=handler.params[fieldName])
                panelSizer.Add(ctrls.nameCtrl, [row, 0])
                panelSizer.Add(ctrls.valueCtrl, [row, 1])
                row += 1
            #store info about the field
            self.staircaseCtrls[fieldName] = ctrls
        return panel
    def getTrialsSummary(self, conditions):
        if type(conditions)==list and len(conditions)>0:
            #get attr names (conditions[0].keys() inserts u'name' and u' is annoying for novice)
            paramStr = "["
            for param in conditions[0]:
                paramStr += (unicode(param)+', ')
            paramStr = paramStr[:-2]+"]"#remove final comma and add ]
            #generate summary info
            return _translate('%(nCondition)i conditions, with %(nParam)i parameters\n%(paramStr)s') \
                % {'nCondition':len(conditions), 'nParam':len(conditions[0]), 'paramStr':paramStr}
        else:
            if self.conditionsFile and not os.path.isfile(self.conditionsFile):
                return  _translate("No parameters set (conditionsFile not found)")
            return _translate("No parameters set")
    def viewConditions(self, event):
        """ display Condition x Parameter values from within a file
        make new if no self.conditionsFile is set
        """
        self.refreshConditions()
        conditions = self.conditions # list of dict
        if self.conditionsFile:
            # get name + dir, like BART/trialTypes.xlsx
            fileName = os.path.abspath(self.conditionsFile)
            fileName = fileName.rsplit(os.path.sep,2)[1:]
            fileName = os.path.join(*fileName)
            if fileName.endswith('.pkl'):
                # edit existing .pkl file, loading from file
                gridGUI = DlgConditions(fileName=self.conditionsFile,
                                            parent=self, title=fileName)
            else:
                # preview existing .csv or .xlsx file that has already been loaded -> conditions
                # better to reload file, get fieldOrder as well
                gridGUI = DlgConditions(conditions, parent=self,
                                        title=fileName, fixed=True)
        else: # edit new empty .pkl file
            gridGUI = DlgConditions(parent=self)
            # should not check return value, its meaningless
            if gridGUI.OK:
                self.conditions = gridGUI.asConditions()
                if hasattr(gridGUI, 'fileName'):
                    self.conditionsFile = gridGUI.fileName
        self.currentHandler.params['conditionsFile'].val = self.conditionsFile
        if 'conditionsFile' in self.currentCtrls.keys(): # as set via DlgConditions
            valCtrl = self.currentCtrls['conditionsFile'].valueCtrl
            valCtrl.Clear()
            valCtrl.WriteText(self.conditionsFile)
        # still need to do namespace and internal updates (see end of onBrowseTrialsFile)

    def setCtrls(self, ctrlType):
        #choose the ctrls to show/hide
        if ctrlType=='staircase':
            self.currentHandler = self.stairHandler
            self.stairPanel.Show()
            self.constantsPanel.Hide()
            self.multiStairPanel.Hide()
            self.currentCtrls = self.staircaseCtrls
        elif ctrlType=='interleaved staircases':
            self.currentHandler = self.multiStairHandler
            self.stairPanel.Hide()
            self.constantsPanel.Hide()
            self.multiStairPanel.Show()
            self.currentCtrls = self.multiStairCtrls
        else:
            self.currentHandler = self.trialHandler
            self.stairPanel.Hide()
            self.constantsPanel.Show()
            self.multiStairPanel.Hide()
            self.currentCtrls = self.constantsCtrls
        self.currentType=ctrlType
        #redo layout
        self.mainSizer.Layout()
        self.Fit()
        self.Refresh()
    def onTypeChanged(self, evt=None):
        newType = evt.GetString()
        if newType==self.currentType:
            return
        self.setCtrls(newType)
    def onBrowseTrialsFile(self, event):
        self.conditionsFileOrig = self.conditionsFile
        self.conditionsOrig = self.conditions
        expFolder,expName = os.path.split(self.frame.filename)
        dlg = wx.FileDialog(self, message=_translate("Open file ..."), style=wx.OPEN,
                            defaultDir=expFolder)
        if dlg.ShowModal() == wx.ID_OK:
            newFullPath = dlg.GetPath()
            if self.conditionsFile:
                oldFullPath = os.path.abspath(os.path.join(expFolder, self.conditionsFile))
                isSameFilePathAndName = (newFullPath==oldFullPath)
            else:
                isSameFilePathAndName = False
            newPath = _relpath(newFullPath, expFolder)
            self.conditionsFile = newPath
            needUpdate = False
            try:
                self.conditions, self.condNamesInFile = data.importConditions(dlg.GetPath(),
                                                        returnFieldNames=True)
                needUpdate = True
            except ImportError as msg:
                msg = unicode(msg)
                if msg.startswith('Could not open'):
                    self.currentCtrls['conditions'].setValue(_translate('Could not read conditions from:\n') + newFullPath.split(os.path.sep)[-1])
                    logging.error('Could not open as a conditions file: %s' % newFullPath)
                else:
                    m2 = msg.replace('Conditions file ', '')
                    dlgErr = dialogs.MessageDialog(parent=self.frame,
                        message=m2.replace(': ', os.linesep * 2), type='Info',
                        title=_translate('Configuration error in conditions file')).ShowModal()
                    self.currentCtrls['conditions'].setValue(
                        _translate('Bad condition name(s) in file:\n') + newFullPath.split(os.path.sep)[-1])
                    logging.error('Rejected bad condition name(s) in file: %s' % newFullPath)
                self.conditionsFile = self.conditionsFileOrig
                self.conditions = self.conditionsOrig
                return # no update or display changes
            duplCondNames = []
            if len(self.condNamesInFile):
                for condName in self.condNamesInFile:
                    if self.exp.namespace.exists(condName):
                        duplCondNames.append(condName)
            # abbrev long strings to better fit in the dialog:
            duplCondNamesStr = ' '.join(duplCondNames)[:42]
            if len(duplCondNamesStr)==42:
                duplCondNamesStr = duplCondNamesStr[:39]+'...'
            if len(duplCondNames):
                if isSameFilePathAndName:
                    logging.info('Assuming reloading file: same filename and duplicate condition names in file: %s' % self.conditionsFile)
                else:
                    self.currentCtrls['conditionsFile'].setValue(newPath)
                    self.currentCtrls['conditions'].setValue(
                        'Warning: Condition names conflict with existing:\n['+duplCondNamesStr+
                        ']\nProceed anyway? (= safe if these are in old file)')
                    logging.warning('Duplicate condition names, different conditions file: %s' % duplCondNamesStr)
            # stash condition names but don't add to namespace yet, user can still cancel
            self.duplCondNames = duplCondNames # add after self.show() in __init__

            if needUpdate or 'conditionsFile' in self.currentCtrls.keys() and not duplCondNames:
                self.currentCtrls['conditionsFile'].setValue(newPath)
                self.currentCtrls['conditions'].setValue(self.getTrialsSummary(self.conditions))

    def getParams(self):
        """Retrieves data and re-inserts it into the handler and returns those handler params
        """
        #get data from input fields
        for fieldName in self.currentHandler.params.keys():
            if fieldName == 'endPoints':
                continue  #this was deprecated in v1.62.00
            param = self.currentHandler.params[fieldName]
            if fieldName in ['conditionsFile']:
                param.val = self.conditionsFile  #not the value from ctrl - that was abbreviated
                # see onOK() for partial handling = check for '...'
            else:#most other fields
                ctrls = self.currentCtrls[fieldName]#the various dlg ctrls for this param
                param.val = ctrls.getValue()#from _baseParamsDlg (handles diff control types)
                if ctrls.typeCtrl:
                    param.valType = ctrls.getType()
                if ctrls.updateCtrl:
                    param.updates = ctrls.getUpdates()
        return self.currentHandler.params
    def refreshConditions(self):
        """user might have manually edited the conditionsFile name, which in turn
        affects self.conditions and namespace. It's harder to handle changes to
        long names that have been abbrev()'d, so skip them (names containing '...').
        """
        val = self.currentCtrls['conditionsFile'].valueCtrl.GetValue()
        if val.find('...')==-1 and self.conditionsFile != val:
            self.conditionsFile = val
            if self.conditions:
                self.exp.namespace.remove(self.conditions[0].keys())
            if os.path.isfile(self.conditionsFile):
                try:
                    self.conditions = data.importConditions(self.conditionsFile)
                    self.currentCtrls['conditions'].setValue(self.getTrialsSummary(self.conditions))
                except ImportError as msg:
                    self.currentCtrls['conditions'].setValue(
                        _translate('Badly formed condition name(s) in file:\n')+str(msg).replace(':','\n')+
                        _translate('.\nNeed to be legal as var name; edit file, try again.'))
                    self.conditions = ''
                    logging.error('Rejected bad condition name in conditions file: %s' % str(msg).split(':')[0])
            else:
                self.conditions = None
                self.currentCtrls['conditions'].setValue(_translate("No parameters set (conditionsFile not found)"))
        else:
            logging.debug('DlgLoop: could not determine if a condition filename was edited')
            #self.currentCtrls['conditions'] could be misleading at this point
    def onOK(self, event=None):
        # intercept OK in case user deletes or edits the filename manually
        if 'conditionsFile' in self.currentCtrls.keys():
            self.refreshConditions()
        event.Skip() # do the OK button press


class DlgComponentProperties(_BaseParamsDlg):
    def __init__(self,frame,title,params,order,
            helpUrl=None, suppressTitles=True,size=wx.DefaultSize,
            style=wx.DEFAULT_DIALOG_STYLE|wx.DIALOG_NO_PARENT,
            editing=False):
        style=style|wx.RESIZE_BORDER
        _BaseParamsDlg.__init__(self,frame,title,params,order,
                                helpUrl=helpUrl,size=size,style=style,
                                editing=editing)
        self.frame=frame
        self.app=frame.app
        self.dpi=self.app.dpi

        #for input devices:
        if 'storeCorrect' in self.params:
            self.onStoreCorrectChange(event=None)#do this just to set the initial values to be
            self.Bind(wx.EVT_CHECKBOX, self.onStoreCorrectChange, self.paramCtrls['storeCorrect'].valueCtrl)

        #for all components
        self.show()
        if self.OK:
            self.params = self.getParams()#get new vals from dlg
        self.Destroy()

    def onStoreCorrectChange(self,event=None):
        """store correct has been checked/unchecked. Show or hide the correctAns field accordingly"""
        if self.paramCtrls['storeCorrect'].valueCtrl.GetValue():
            self.paramCtrls['correctAns'].valueCtrl.Show()
            self.paramCtrls['correctAns'].nameCtrl.Show()
            #self.paramCtrls['correctAns'].typeCtrl.Show()
            #self.paramCtrls['correctAns'].updateCtrl.Show()
        else:
            self.paramCtrls['correctAns'].valueCtrl.Hide()
            self.paramCtrls['correctAns'].nameCtrl.Hide()
            #self.paramCtrls['correctAns'].typeCtrl.Hide()
            #self.paramCtrls['correctAns'].updateCtrl.Hide()
        self.mainSizer.Layout()
        self.Fit()
        self.Refresh()


class DlgExperimentProperties(_BaseParamsDlg):
    def __init__(self,frame,title,params,order,suppressTitles=False,
            size=wx.DefaultSize,helpUrl=None,
            style=wx.DEFAULT_DIALOG_STYLE|wx.DIALOG_NO_PARENT):
        style=style|wx.RESIZE_BORDER
        _BaseParamsDlg.__init__(self,frame,'Experiment Settings',params,order,
                                size=size,style=style,helpUrl=helpUrl)
        self.frame=frame
        self.app=frame.app
        self.dpi=self.app.dpi

        #for input devices:
        self.onFullScrChange(event=None)#do this just to set the initial values to be
        self.Bind(wx.EVT_CHECKBOX, self.onFullScrChange, self.paramCtrls['Full-screen window'].valueCtrl)

        #for all components
        self.show()
        if self.OK:
            self.params = self.getParams()#get new vals from dlg
        self.Destroy()

    def onFullScrChange(self,event=None):
        """full-screen has been checked/unchecked. Show or hide the window size field accordingly"""
        if self.paramCtrls['Full-screen window'].valueCtrl.GetValue():
            #get screen size for requested display
            num_displays = wx.Display.GetCount()
            try:
                screen_value=int(self.paramCtrls['Screen'].valueCtrl.GetValue())
            except ValueError:
                screen_value=1#param control currently contains no integer value
            if screen_value<1 or screen_value>num_displays:
                logging.error("User requested non-existent screen")
                screenN=0
            else:
                screenN=screen_value-1
            size=list(wx.Display(screenN).GetGeometry()[2:])
            #set vals and disable changes
            self.paramCtrls['Window size (pixels)'].valueCtrl.SetValue(unicode(size))
            self.paramCtrls['Window size (pixels)'].valueCtrl.Disable()
            self.paramCtrls['Window size (pixels)'].nameCtrl.Disable()
        else:
            self.paramCtrls['Window size (pixels)'].valueCtrl.Enable()
            self.paramCtrls['Window size (pixels)'].nameCtrl.Enable()
        self.mainSizer.Layout()
        self.Fit()
        self.Refresh()

    def show(self):
        """Adds an OK and cancel button, shows dialogue.

        This method returns wx.ID_OK (as from ShowModal), but also
        sets self.OK to be True or False
        """
        #add buttons for help, OK and Cancel
        self.mainSizer=wx.BoxSizer(wx.VERTICAL)
        buttons = wx.StdDialogButtonSizer()
        if self.helpUrl!=None:
            helpBtn = wx.Button(self, wx.ID_HELP, _translate(" Help "))
            helpBtn.SetHelpText(_translate("Get help about this component"))
            helpBtn.Bind(wx.EVT_BUTTON, self.onHelp)
            buttons.Add(helpBtn, 0, wx.ALIGN_RIGHT|wx.ALL,border=3)
        self.OKbtn = wx.Button(self, wx.ID_OK, _translate(" OK "))
        self.OKbtn.SetDefault()
        buttons.Add(self.OKbtn, 0, wx.ALIGN_RIGHT|wx.ALL,border=3)
        CANCEL = wx.Button(self, wx.ID_CANCEL, _translate(" Cancel "))
        buttons.Add(CANCEL, 0, wx.ALIGN_RIGHT|wx.ALL,border=3)

        buttons.Realize()
        self.ctrls.Fit()
        self.mainSizer.Add(self.ctrls)
        self.mainSizer.Add(buttons, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(self.mainSizer)

        #move the position to be v near the top of screen and to the right of the left-most edge of builder
        builderPos = self.frame.GetPosition()
        self.SetPosition((builderPos[0]+200,20))

        #do show and process return
        retVal = self.ShowModal()
        if retVal== wx.ID_OK: self.OK=True
        else:  self.OK=False
        return wx.ID_OK

