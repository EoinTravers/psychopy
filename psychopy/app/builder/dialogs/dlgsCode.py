#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2015 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

"""Dialog classes for the Builder Code component
"""

from __future__ import (absolute_import, print_function, division)

import keyword
import re
import wx
from wx.lib import flatnotebook

from .. import validators

_unescapedDollarSign_re = re.compile(r"^\$|[^\\]\$")


class DlgCodeComponentProperties(wx.Dialog):
    def __init__(self,frame,title,params,order,
            helpUrl=None, suppressTitles=True,size=wx.DefaultSize,
            style=(wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
                            | wx.THICK_FRAME | wx.DIALOG_NO_PARENT),
            editing=False):

        # translate title
        localizedTitle = title.replace(' Properties',_translate(' Properties'))

        wx.Dialog.__init__(self, frame,-1,localizedTitle,size=size,style=style)
        self.frame=frame
        self.app=frame.app
        self.helpUrl=helpUrl
        self.params=params   #dict
        self.order=order
        self.title = title
        self.localizedTitle = localizedTitle # keep localized title to update dialog's properties later.
        self.code_gui_elements={}
        if not editing and 'name' in self.params.keys():
            # then we're adding a new component, so provide a known-valid name:
            self.params['name'].val = self.frame.exp.namespace.makeValid(params['name'].val)


        agwStyle = flatnotebook.FNB_NO_X_BUTTON
        if hasattr(flatnotebook, "FNB_NAV_BUTTONS_WHEN_NEEDED"):
            # not available in wxPython 2.8
            agwStyle |= flatnotebook.FNB_NAV_BUTTONS_WHEN_NEEDED
        if hasattr(flatnotebook, "FNB_NO_TAB_FOCUS"):
            # not available in wxPython 2.8.10
            agwStyle |= flatnotebook.FNB_NO_TAB_FOCUS
        self.code_sections = flatnotebook.FlatNotebook(self, wx.ID_ANY,
            style = agwStyle)

        openToPage = 0
        for i, pkey in enumerate(self.order):
            param=self.params.get(pkey)
            if pkey == 'name':
                self.name_label = wx.StaticText(self, wx.ID_ANY,param.label)
                self.component_name = wx.TextCtrl(self,
                                 wx.ID_ANY,
                                 unicode(param.val),
                                 style=wx.TE_PROCESS_ENTER | wx.TE_PROCESS_TAB)
                self.component_name.SetToolTipString(param.hint)
                self.component_name.SetValidator(validators.NameValidator())
                self.nameOKlabel=wx.StaticText(self,-1,'',
                                            style=wx.ALIGN_RIGHT)
                self.nameOKlabel.SetForegroundColour(wx.RED)
            else:
                guikey=pkey.replace(' ','_')
                param_gui_elements=self.code_gui_elements.setdefault(guikey,
                                                                     dict())

                panel_element=param_gui_elements.setdefault(guikey+'_panel',
                                       wx.Panel(self.code_sections, wx.ID_ANY))
                code_box=param_gui_elements.setdefault(guikey+'_codebox',
                                              CodeBox(panel_element,
                                                    wx.ID_ANY,
                                                    pos=wx.DefaultPosition,
                                                    style=0,
                                                    prefs=self.app.prefs))
                if len(param.val):
                    code_box.AddText(unicode(param.val))
                if len(param.val.strip()) and not openToPage:
                        openToPage = i  # first non-blank page

        if self.helpUrl!=None:
            self.help_button = wx.Button(self, wx.ID_HELP, _translate(" Help "))
            self.help_button.SetToolTip(wx.ToolTip(_translate("Go to online help about this component")))
        self.ok_button = wx.Button(self, wx.ID_OK, _translate(" OK "))
        self.ok_button.SetDefault()
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, _translate(" Cancel "))

        self.__set_properties()
        self.__do_layout()
        self.code_sections.SetSelection(max(0, openToPage - 1))

        self.Bind(wx.EVT_BUTTON, self.helpButtonHandler, self.help_button)

        #do show and process return
        ret=self.ShowModal()

        if ret == wx.ID_OK:
            self.checkName()
            self.OK=True
            self.params = self.getParams()#get new vals from dlg
            self.Validate()
            # TODO: Should code from each code section tab have syntax checked??
        else:
            self.OK=False

    def checkName(self, event=None):
        """
        Issue a form validation on name change.
        """
        self.Validate()

    def __set_properties(self):

        self.SetTitle(self.localizedTitle) # use localized title
        self.SetSize((640, 480))

    def __do_layout(self):
        for param_name in self.order:
             if param_name.lower() != 'name':
                guikey=param_name.replace(' ','_')
                param_gui_dict=self.code_gui_elements.get(guikey)
                asizer=param_gui_dict.setdefault(guikey+'_sizer',wx.BoxSizer(wx.VERTICAL))
                asizer.Add(param_gui_dict.get(guikey+'_codebox'), 1, wx.EXPAND, 0)
                param_gui_dict.get(guikey+'_panel').SetSizer(asizer)
                self.code_sections.AddPage(param_gui_dict.get(guikey+'_panel'), _translate(param_name))

        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_sizer.Add(self.name_label, 0, wx.ALL, 10)
        name_sizer.Add(self.component_name, 0,  wx.BOTTOM | wx.TOP, 10)
        name_sizer.Add(self.nameOKlabel, 0,  wx.ALL, 10)

        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_1.Add(name_sizer)
        sizer_1.Add(self.code_sections, 1, wx.EXPAND |wx.ALL, 10)
        sizer_2.Add(self.help_button, 0, wx.RIGHT, 10)
        sizer_2.Add(self.ok_button, 0, wx.LEFT, 10)
        sizer_2.Add(self.cancel_button, 0, 0, 0)
        sizer_1.Add(sizer_2, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        self.SetSizer(sizer_1)
        self.Layout()
        self.Center()

    def getParams(self):
        """retrieves data from any fields in self.code_gui_elements
        (populated during the __init__ function)

        The new data from the dlg get inserted back into the original params
        used in __init__ and are also returned from this method.
        """
        #get data from input fields
        for fieldName in self.params.keys():
            param=self.params[fieldName]
            if fieldName=='name':
                param.val = self.component_name.GetValue()
            else:
                guikey=fieldName.replace(' ','_')
                cb_gui_el=guikey+'_codebox'
                if guikey in self.code_gui_elements:

                    param.val=self.code_gui_elements.get(guikey).get(cb_gui_el).GetText()
        return self.params

    def helpButtonHandler(self, event):
        """Uses self.app.followLink() to self.helpUrl
        """
        self.app.followLink(url=self.helpUrl)


class CodeBox(wx.stc.StyledTextCtrl):
    # this comes mostly from the wxPython demo styledTextCtrl 2
    def __init__(self, parent, ID, prefs,
                 pos=wx.DefaultPosition, size=wx.Size(100,160),#set the viewer to be small, then it will increase with wx.aui control
                 style=0):
        wx.stc.StyledTextCtrl.__init__(self, parent, ID, pos, size, style)
        #JWP additions
        self.notebook=parent
        self.prefs = prefs
        self.UNSAVED=False
        self.filename=""
        self.fileModTime=None # for checking if the file was modified outside of CodeEditor
        self.AUTOCOMPLETE = True
        self.autoCompleteDict={}
        #self.analyseScript()  #no - analyse after loading so that window doesn't pause strangely
        self.locals = None #this will contain the local environment of the script
        self.prevWord=None
        #remove some annoying stc key commands
        self.CmdKeyClear(ord('['), wx.stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord(']'), wx.stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord('/'), wx.stc.STC_SCMOD_CTRL)
        self.CmdKeyClear(ord('/'), wx.stc.STC_SCMOD_CTRL|wx.stc.STC_SCMOD_SHIFT)

        self.SetLexer(wx.stc.STC_LEX_PYTHON)
        self.SetKeyWords(0, " ".join(keyword.kwlist))

        self.SetProperty("fold", "1")
        self.SetProperty("tab.timmy.whinge.level", "4")#4 means 'tabs are bad'; 1 means 'flag inconsistency'
        self.SetMargins(0,0)
        self.SetUseTabs(False)
        self.SetTabWidth(4)
        self.SetIndent(4)
        self.SetViewWhiteSpace(self.prefs.appData['coder']['showWhitespace'])
        #self.SetBufferedDraw(False)
        self.SetViewEOL(False)
        self.SetEOLMode(wx.stc.STC_EOL_LF)
        self.SetUseAntiAliasing(True)
        #self.SetUseHorizontalScrollBar(True)
        #self.SetUseVerticalScrollBar(True)

        #self.SetEdgeMode(wx.stc.STC_EDGE_BACKGROUND)
        #self.SetEdgeMode(wx.stc.STC_EDGE_LINE)
        #self.SetEdgeColumn(78)

        # Setup a margin to hold fold markers
        self.SetMarginType(2, wx.stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(2, wx.stc.STC_MASK_FOLDERS)
        self.SetMarginSensitive(2, True)
        self.SetMarginWidth(2, 12)
        self.Bind(wx.stc.EVT_STC_MARGINCLICK, self.OnMarginClick)

        self.SetIndentationGuides(False)

        # Like a flattened tree control using square headers
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDEROPEN,    wx.stc.STC_MARK_BOXMINUS,          "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDER,        wx.stc.STC_MARK_BOXPLUS,           "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDERSUB,     wx.stc.STC_MARK_VLINE,             "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDERTAIL,    wx.stc.STC_MARK_LCORNER,           "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDEREND,     wx.stc.STC_MARK_BOXPLUSCONNECTED,  "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDEROPENMID, wx.stc.STC_MARK_BOXMINUSCONNECTED, "white", "#808080")
        self.MarkerDefine(wx.stc.STC_MARKNUM_FOLDERMIDTAIL, wx.stc.STC_MARK_TCORNER,           "white", "#808080")

        #self.DragAcceptFiles(True)
        #self.Bind(wx.EVT_DROP_FILES, self.coder.filesDropped)
        #self.Bind(wx.stc.EVT_STC_MODIFIED, self.onModified)
        ##self.Bind(wx.stc.EVT_STC_UPDATEUI, self.OnUpdateUI)
        #self.Bind(wx.stc.EVT_STC_MARGINCLICK, self.OnMarginClick)
        #self.Bind(wx.EVT_KEY_DOWN, self.OnKeyPressed)
        #self.SetDropTarget(FileDropTarget(coder = self.coder))

        self.setupStyles()

    def setupStyles(self):

        if wx.Platform == '__WXMSW__':
            faces = { 'size' : 10}
        elif wx.Platform == '__WXMAC__':
            faces = { 'size' : 14}
        else:
            faces = { 'size' : 12}
        if self.prefs.coder['codeFontSize']:
            faces['size'] = int(self.prefs.coder['codeFontSize'])
        faces['small']=faces['size']-2
        # Global default styles for all languages
        faces['code'] = self.prefs.coder['codeFont']#,'Arial']#use arial as backup
        faces['comment'] = self.prefs.coder['commentFont']#,'Arial']#use arial as backup
        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT,     "face:%(code)s,size:%(size)d" % faces)
        self.StyleClearAll()  # Reset all to be like the default

        # Global default styles for all languages
        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT,     "face:%(code)s,size:%(size)d" % faces)
        self.StyleSetSpec(wx.stc.STC_STYLE_LINENUMBER,  "back:#C0C0C0,face:%(code)s,size:%(small)d" % faces)
        self.StyleSetSpec(wx.stc.STC_STYLE_CONTROLCHAR, "face:%(comment)s" % faces)
        self.StyleSetSpec(wx.stc.STC_STYLE_BRACELIGHT,  "fore:#FFFFFF,back:#0000FF,bold")
        self.StyleSetSpec(wx.stc.STC_STYLE_BRACEBAD,    "fore:#000000,back:#FF0000,bold")

        # Python styles
        # Default
        self.StyleSetSpec(wx.stc.STC_P_DEFAULT, "fore:#000000,face:%(code)s,size:%(size)d" % faces)
        # Comments
        self.StyleSetSpec(wx.stc.STC_P_COMMENTLINE, "fore:#007F00,face:%(comment)s,size:%(size)d" % faces)
        # Number
        self.StyleSetSpec(wx.stc.STC_P_NUMBER, "fore:#007F7F,size:%(size)d" % faces)
        # String
        self.StyleSetSpec(wx.stc.STC_P_STRING, "fore:#7F007F,face:%(code)s,size:%(size)d" % faces)
        # Single quoted string
        self.StyleSetSpec(wx.stc.STC_P_CHARACTER, "fore:#7F007F,face:%(code)s,size:%(size)d" % faces)
        # Keyword
        self.StyleSetSpec(wx.stc.STC_P_WORD, "fore:#00007F,bold,size:%(size)d" % faces)
        # Triple quotes
        self.StyleSetSpec(wx.stc.STC_P_TRIPLE, "fore:#7F0000,size:%(size)d" % faces)
        # Triple double quotes
        self.StyleSetSpec(wx.stc.STC_P_TRIPLEDOUBLE, "fore:#7F0000,size:%(size)d" % faces)
        # Class name definition
        self.StyleSetSpec(wx.stc.STC_P_CLASSNAME, "fore:#0000FF,bold,underline,size:%(size)d" % faces)
        # Function or method name definition
        self.StyleSetSpec(wx.stc.STC_P_DEFNAME, "fore:#007F7F,bold,size:%(size)d" % faces)
        # Operators
        self.StyleSetSpec(wx.stc.STC_P_OPERATOR, "bold,size:%(size)d" % faces)
        # Identifiers
        self.StyleSetSpec(wx.stc.STC_P_IDENTIFIER, "fore:#000000,face:%(code)s,size:%(size)d" % faces)
        # Comment-blocks
        self.StyleSetSpec(wx.stc.STC_P_COMMENTBLOCK, "fore:#7F7F7F,size:%(size)d" % faces)
        # End of line where string is not closed
        self.StyleSetSpec(wx.stc.STC_P_STRINGEOL, "fore:#000000,face:%(code)s,back:#E0C0E0,eol,size:%(size)d" % faces)

        self.SetCaretForeground("BLUE")
    def setStatus(self, status):
        if status=='error':
            color=(255,210,210,255)
        elif status=='changed':
            color=(220,220,220,255)
        else:
            color=(255,255,255,255)
        self.StyleSetBackground(wx.stc.STC_STYLE_DEFAULT, color)
        self.setupStyles()#then reset fonts again on top of that color
    def OnMarginClick(self, evt):
        # fold and unfold as needed
        if evt.GetMargin() == 2:
            lineClicked = self.LineFromPosition(evt.GetPosition())

            if self.GetFoldLevel(lineClicked) & wx.stc.STC_FOLDLEVELHEADERFLAG:
                if evt.GetShift():
                    self.SetFoldExpanded(lineClicked, True)
                    self.Expand(lineClicked, True, True, 1)
                elif evt.GetControl():
                    if self.GetFoldExpanded(lineClicked):
                        self.SetFoldExpanded(lineClicked, False)
                        self.Expand(lineClicked, False, True, 0)
                    else:
                        self.SetFoldExpanded(lineClicked, True)
                        self.Expand(lineClicked, True, True, 100)
                else:
                    self.ToggleFold(lineClicked)
