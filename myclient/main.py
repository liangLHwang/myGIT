#-*- coding:utf-8 -*-
# My Kivy client to receive arduino info and to show on the screen
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.config import Config
from kivy.graphics import Color, Line
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivy.uix.behaviors import ToggleButtonBehavior
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

import time
from math import ceil
import socket
import traceback

Builder.load_file("myclient.kv")

def Log2File(text, clr = False, file_name = "log.txt"):
    if clr:
        s = 'w'
    else:
        s = 'a'
    fid = open(file_name, s)
    time_str = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    fid.write(time_str+':'+text+'\n')
    fid.close()
    return

def MYLOG(text, mode = 0):
    if mode == 0:
        print(text)
    elif mode == 1:
        Log2File(text)
    else:
        pass

class RfidComm:
    """This class communicate with the rfid module"""
    #def __init__(self, arg):
        #super(RfidComm, self).__init__()
        #self.arg = arg
    def __init__(self):
        self.n_rx_msg = 0
        self.epc_all = []
        self.data_recv = []
        self.epc_target = ""
        self.host = '192.168.4.1'    # The remote host
        self.port = 333              # The same port as used by the server
        self.is_connected = False
        self.rssi = -80
        self.t = 0
        self.s = None
        self.epc_id_w = ''
        self.epc_note_w = ''
        self.last_cmd = 0
        self.dummy_data = True

    def ConnectRfidModule(self):
        self.is_connected = True
        self.data_recv = []
        if not self.dummy_data:
            try:
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.s.connect((self.host, self.port))
                self.is_connected = True
            except socket.error:
                MYLOG("could not open socket")
            else:
                MYLOG("connected!")
        return

    def DisconnectRfidModule(self):
        self.is_connected = False
        if self.s:
            self.s.close()
            self.s = None

    def TxToServer(self, cmd_id):
        if cmd_id >= 0 and cmd_id <= 3:
            if cmd_id == 0:
                send_msg = 'BEAT:     \n'
            elif cmd_id == 1:
                send_msg = "ASK rssi: "+str(self.n_rx_msg)+"\n"
            elif cmd_id == 2:
                send_msg = 'READ tags.\n'
            elif cmd_id == 3:
                send_msg = 'WRITE:'+self.epc_id_w+';'+self.epc_note_w+'.'+'\n'
                MYLOG(send_msg)
            else:
                send_msg = ''
            self.last_cmd = cmd_id
            if not self.dummy_data:
                try:
                    self.s.sendall(send_msg)
                #except socket.error:
                except Exception, e:
                    MYLOG('TX Connection fail!')
                    MYLOG('traceback.format_exc():\n%s' % traceback.format_exc())
        return

    def RxFromServer(self):
        if self.dummy_data:
            self.DummyData()
        else:
            try:
                BUFSIZE = 1024
                #send_msg = "ASK rssi: "+str(self.n_rx_msg)+"\n"
                #self.s.sendall(send_msg.encode())
                recv_msg = self.s.recv(BUFSIZE)
                if not recv_msg:
                    MYLOG("Connection break!")
                    self.DisconnectRfidModule()
                else:
                    MYLOG(recv_msg)
                    self.n_rx_msg += 1
                    self.DecodeMsg(recv_msg)
            #except socket.error:
            except Exception, e:
                MYLOG('RX Connection fail!')
                MYLOG('traceback.format_exc():\n%s' % traceback.format_exc())
        return

    def DecodeMsg(self, msg):
        #RSSI format: A55A?epc1:time_start;time_d1:rss1;time_d1:rss1;time_d1:rss1;?epc2:time_start;epc='wrong' is a special case
        #tag read resp format: B44B?epc1:user_note1?epc2:user_note2... epc='wrong' means no tag found
        #tag write resp format: C33C?OK/fail
        #heart beat format: F00F?xxx
        block_items = msg.split('?')
        if block_items[0] == 'A55A':
            for b in range(1, len(block_items)):
                items = block_items[b].split(';')
                sub_items = items[0].split(':')
                epc_rx = sub_items[0]
                #t_rx_base = float(sub_items[1])
                t_rx_base = int(sub_items[1])/1000.0
                if epc_rx == "wrong":
                    rec_type = 1
                    rec = {}
                    rec['type'] = rec_type
                    rec['time'] = t_rx_base
                    rec['rssi'] = -100
                    self.data_recv.append(rec)
                else:
                    if epc_rx not in self.epc_all:
                        self.epc_all.append(epc_rx)
                        sm.get_screen('epc').ids.m_grid.DisplayData(self.epc_all)
                    if len(self.epc_target) < 20:
                        self.epc_target = epc_rx
                        sm.get_screen('main').ids.tag_id.text = "EPC: "+self.epc_target
                    if self.epc_target == epc_rx:
                        rec_type = 0
                    else:
                        rec_type = 2
                    for i in range(1, len(items)):
                        if items[i].find(':') < 0:
                            break
                        else:
                            sub_items = items[i].split(':')
                            #t_delta = float(sub_items[0])
                            t_delta = int(sub_items[0])/1000.0
                            rssi = int(sub_items[1])
                            rec = {}
                            rec['epc'] = epc_rx
                            rec['type'] = rec_type
                            rec['time'] = t_rx_base + t_delta
                            rec['rssi'] = rssi
                            self.data_recv.append(rec)
        elif block_items[0] == 'B44B':
            self.epc_all = []
            epc_recs = []
            for b in range(1, len(block_items)):
                items = block_items[b].split(':')
                epc_rx = items[0]
                epc_note = items[1]
                if epc_rx == "wrong":
                    MYLOG('no tag is found.')
                else:
                    MYLOG(epc_rx+':'+epc_note)
                    self.epc_all.append(epc_rx+':'+epc_note)
                    epc_recs.append([epc_rx, epc_note])
            sm.get_screen('epc').ids.m_grid.DisplayData(self.epc_all)
            sm.get_screen('lists').AddEPCRecord(epc_recs)
            sm.get_screen('lists').UpdateGrid()
            sm.get_screen('lists').SaveToFile()
        elif block_items[0] == 'C33C':
            MYLOG('write tag: '+block_items[1])
            sm.get_screen('epc').ids.epc_top.text = 'write tag: '+self.epc_id_w+':'+self.epc_note_w+': '+block_items[1]
            sm.get_screen('epc').ReadTags()
        elif block_items[0] == 'F00F':
            #MYLOG("Heart beat packet")
            pass
        else:
            MYLOG("wrong package format!")
            return
        return

    def DummyData(self):
        # virtually generated data for testing
        self.n_rx_msg += 1
        if self.last_cmd == 1:
            for i in range(25):
                rec = {}
                rec['type'] = 0
                rec['time'] = self.t + 0.01*i
                rec['rssi'] = self.rssi
                rec['epc'] = '112233445566778899AABBCC'
                self.data_recv.append(rec)
            self.t += 0.25
            self.rssi += 10
            if self.rssi > -40: self.rssi -= 50
        elif self.last_cmd == 2:
            recv_msg = 'B44B?112233445566778899AABBCC:table'+str(self.n_rx_msg)
            recv_msg += '?111111111111111111111111:chair'+str(self.n_rx_msg)
            recv_msg += '?xxxxxxxxxxxxxxxxxxxxxxxx:haha'+str(self.n_rx_msg)
            self.DecodeMsg(recv_msg)
        elif self.last_cmd == 3:
            recv_msg = 'C33C?OK'
            self.DecodeMsg(recv_msg)
        else:
            pass
        return

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.rfid = RfidComm()
        self.bind(size=self.onUpdateSize)
        Clock.schedule_interval(self.onUpdateAtTick, 0.25)
        MYLOG("start 1s event")
        self.line_width = 2
        self.is_showing = False
        self.is_showing_s = self.is_showing
    '''
    def on_touch_down(self, touch):
        if Widget.on_touch_down(self, touch):
            return
        with self.canvas:
            Color(*get_color_from_hex('#0080FF80'))
            touch.ud['current_line'] = Line(
                points=(touch.x, touch.y), width=self.line_width)

    def on_touch_move(self, touch):
        if 'current_line' in touch.ud:
            touch.ud['current_line'].points += (
                touch.x, touch.y)
    '''
    def ClearCanvas(self):
        saved = self.children[:]
        self.clear_widgets()
        self.canvas.clear()
        for widget in saved:
            self.add_widget(widget)
        self.DrawAxis()

    def DrawAxis(self):
        with self.canvas:
            Color(*get_color_from_hex('#000000FF'))
            self.origin_x = int(self.width * 0.1)
            self.origin_y = int(self.height * 0.9)
            self.length_x = int(self.width * 0.8)
            self.length_y = int(self.height * 0.6)
            #print self.origin_x, self.origin_y, self.length_x, self.length_y
            Line(points = (self.origin_x, self.origin_y, self.origin_x, self.origin_y-self.length_y, self.origin_x+self.length_x, self.origin_y-self.length_y), width=2)

    def onUpdateSize(self, *args):
        self.ClearCanvas()
        self.DrawAxis()
        if self.width > 480*2:
            self.line_width = ceil(self.width/960.0)*2
        else:
            self.line_width = 2
        Log2File("width="+str(self.width)+"|line_width="+str(self.line_width))

    def onUpdateAtTick(self, nap):
        if self.rfid.is_connected:
            if self.is_showing:
                self.rfid.TxToServer(1)
                #MYLOG("----")
                self.ClearCanvas()
                self.DrawAxis()
                self.ShowData()
            else:
                self.rfid.TxToServer(0)
            self.rfid.RxFromServer()
        return

    def ShowData(self):
        if len(self.rfid.data_recv) > 0:
            t_range = self.length_x*10.0/self.width
            for item in self.rfid.data_recv:
                if self.rfid.data_recv[-1]['time'] - item['time'] > t_range:
                    self.rfid.data_recv.remove(item)
            t_start = self.rfid.data_recv[-1]['time'] - t_range
            for i in range(len(self.rfid.data_recv)):
                t = self.rfid.data_recv[i]['time']
                if t >= t_start:
                    rssi = self.rfid.data_recv[i]['rssi']
                    px = int((t-t_start)*0.1*self.width) + self.origin_x
                    py = int((rssi+40)*0.1*0.1*self.height) + self.origin_y
                    #print t,rssi,px,py
                    if self.rfid.data_recv[i]['type'] == 0: # target EPC
                        c = '#FF0000FF'
                    elif self.rfid.data_recv[i]['type'] == 1: # no EPC found
                        c = '#00FF00FF'
                    elif self.rfid.data_recv[i]['type'] == 2: # other EPC
                        c = '#0000FFFF'
                    else:
                        c = '#000000FF'
                    if self.rfid.data_recv[i]['type'] == 0 or self.rfid.data_recv[i]['type'] == 1:
                        self.canvas.add(Color(*get_color_from_hex(c)))
                        #self.canvas.add(Line(circle=(px, py, self.line_width), width=self.line_width))
                        self.canvas.add(Line(points=(px, py, px+1, py), width=self.line_width))

    def connect_disconnect(self):
        try:
            if self.rfid.is_connected:
                self.rfid.DisconnectRfidModule()
                self.ids.rfid_reader_connect.text = 'Connect'
                if self.is_showing:
                    self.start_stop()
            else:
                self.rfid.ConnectRfidModule()
                self.ids.rfid_reader_connect.text = 'DisConnect'
        except Exception, e:
            MYLOG('connect fail!')
            MYLOG('traceback.format_exc():\n%s' % traceback.format_exc())

    def start_stop(self):
        self.is_showing = not self.is_showing
        if self.is_showing:
            self.ids.rfid_rx.text = 'Stop'
        else:
            self.ids.rfid_rx.text = 'Start'

    def ReadWriteTags(self):
        self.is_showing_s = self.is_showing
        self.is_showing = False
        sm.current = 'epc'

    def ManageTags(self):
        self.is_showing_s = self.is_showing
        self.is_showing = False
        sm.current = 'lists'

    def WriteTagNote(self):
        '''
        #sm.get_screen('epc').ids.epc_top.text = sm.get_screen('epc').ids.w_text_epc_note.text
        Log2File('write note: ')
        #MYLOG(sm.get_screen('epc').ids.w_text_epc_note.text)
        Log2File(sm.get_screen('epc').ids.w_text_epc_note.text)
        old_text = sm.get_screen('epc').ids.w_text_epc_note.text
        new_text = old_text + '好'
        sm.get_screen('epc').ids.w_text_epc_note.text = new_text
        '''
        self.rfid.epc_id_w = sm.get_screen('epc').ids.w_text_epc_id.text
        self.rfid.epc_note_w = sm.get_screen('epc').ids.w_text_epc_note.text
        MYLOG(self.rfid.epc_note_w)
        self.rfid.TxToServer(3)
        self.rfid.RxFromServer()
        return

class myEPCButton(ToggleButton):
    pass


class MyGrid(GridLayout):

    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.InitEPCData()
        self.DisplayData(self.data)

    def InitEPCData(self):
        self.data = []
        for i in range(5):
            self.data.append("EPC "+str(i)+":Note")

    def DisplayData(self, rec_list):
        self.clear_widgets()
        for i in range(10):
            if i < len(rec_list):
                item = myEPCButton(text=rec_list[i], group = "found_epcs")
                self.add_widget(item)
            else:
                item = Label(text=" ")
                self.add_widget(item)

class RWScreen(Screen):
    def MyOnState(self, togglebutton):
        tb = togglebutton
        #print(tb,tb.state,tb.text)
        if tb.state == 'down':
            items = tb.text.split(':')
            epc12 = items[0]
            if len(items) > 1:
                epc_note = items[1]
            else:
                epc_note = 'NA'
            self.ids.epc_top.text = "SELECTED: "+epc12
            sm.get_screen('main').ids.tag_id.text = "EPC: "+epc12
            sm.get_screen('main').rfid.epc_target = epc12
            self.ids.w_text_epc_id.text = epc12
            self.ids.w_text_epc_note.text = epc_note

    def Back2Main(self):
        sm.get_screen('main').is_showing = sm.get_screen('main').is_showing_s
        sm.current = 'main'
    def ReadTags(self):
        if not sm.get_screen('main').rfid.is_connected:
            sm.get_screen('main').connect_disconnect()
        sm.get_screen('main').rfid.TxToServer(2)
        sm.get_screen('main').rfid.RxFromServer()

class MyListButton(Button):
    def __init__(self,**kwargs):
        super(MyListButton,self).__init__(**kwargs)
        self.epc_id = ''
        self.epc_note = 'NA'

    def on_release(self):
        sm.get_screen('lists').onClickEPCButton(self)

class MyGrid2(GridLayout):

    def __init__(self, **kwargs):
        super(MyGrid2, self).__init__(**kwargs)
        # add button into that grid
        for i in range(30):
            lbl = Label(text=str(i), size=(50, 40), size_hint=(None, None), color=get_color_from_hex('#000000'))
            self.add_widget(lbl)
            btn = MyListButton(text='notes:'+str(i), size=(400, 40), size_hint=(None, None))
            btn.epc_id = str(i)*12
            btn.epc_note = str(i)+' notes'
            self.add_widget(btn)
        self.bind(minimum_height=self.setter('height'))

    def DisplayData(self, epc_list):
        self.clear_widgets()
        for i in range(len(epc_list)):
            lbl = Label(text=str(i), size=(50, 40), size_hint=(None, None), color=get_color_from_hex('#000000'))
            self.add_widget(lbl)
            btn = MyListButton(text=epc_list[i][1], size=(400, 40), size_hint=(None, None))
            btn.epc_id = epc_list[i][0]
            btn.epc_note = epc_list[i][1]
            self.add_widget(btn)


class ListScreen(Screen):
    def __init__(self, **kwargs):
        super(ListScreen, self).__init__(**kwargs)
        self.epc_id = ''
        self.epc_note = 'NA'
        self.epc_list_all = []
        self.rec_file_name = ''
        self.LoadFromFile()

    def LoadFromFile(self, file_name = './tag_data.txt'):
        fid = open(file_name,'r')
        self.rec_file_name = file_name
        try:
            lines = fid.readlines()
            for line in lines:
                items = line.strip('\n').split(':')
                if len(items) == 2:
                    #print(items[0]+':'+items[1]+'.')
                    self.AddEPCRecord([[items[0], items[1]]])
        finally:
            fid.close()
        self.UpdateGrid()

    def UpdateGrid(self):
        epc_filtered = self.FilterTags(self.ids.note_to_find.text)
        self.ids.grid_lists.DisplayData(epc_filtered)

    def AddEPCRecord(self, recs):
        for ritem in recs:
            if len(ritem) == 2:
                if len(ritem[1]) > 0:
                    rec = [ritem[0], ritem[1]]
                else:
                    rec = [ritem[0], 'NA']
                for r in self.epc_list_all:
                    if r[0] == rec[0]: #epc is the same
                        self.epc_list_all.remove(r)
                        MYLOG("replace "+r[0]+':'+r[1]+'.')
                        break
                self.epc_list_all.append(rec)
                MYLOG("add "+rec[0]+':'+rec[1]+'.')

    def SaveToFile(self, file_name = './tag_data.txt'):
        MYLOG("saving to file:"),
        MYLOG(len(self.epc_list_all))
        fid = open(file_name,'w')
        for item in self.epc_list_all:
            fid.write(item[0]+':'+item[1]+'\n')
        fid.close()

    def FilterTags(self, rule):
        res = []
        r_items = rule.split('*')
        for rec in self.epc_list_all:
            is_match = True
            for ri in r_items:
                if len(ri)>0 and rec[1].find(ri) < 0:
                    is_match = False
                    break
            if is_match:
                res.append(rec)
        return(res)

    def Back2Main(self):
        sm.get_screen('main').is_showing = sm.get_screen('main').is_showing_s
        sm.current = 'main'

    def SelTargetEPC(self):
        if len(self.epc_id) == 24:
            sm.get_screen('main').rfid.epc_target = self.epc_id
            sm.get_screen('main').ids.tag_id.text = self.epc_note +'('+ self.epc_id +')'
        self.Back2Main()

    def onClickEPCButton(self, MyListButton):
        mb = MyListButton
        self.ids.lists_info.text = "Select target tag: "+mb.epc_note+'('+mb.epc_id+')'
        self.epc_id = mb.epc_id
        self.epc_note = mb.epc_note

    def onFindTags(self):
        self.UpdateGrid()

# Create the screen manager
sm = ScreenManager()
sm.add_widget(MainScreen(name='main'))
sm.add_widget(RWScreen(name='epc'))
sm.add_widget(ListScreen(name='lists'))

class MyClientApp(App):
    def build(self):
        return sm

if __name__ == '__main__':
    from kivy.core.window import Window
    Window.clearcolor = get_color_from_hex('#FFFFFF')
    Log2File("Application Start", clr=True)
    Window.size=(960,540)#窗口大小
    MyClientApp().run()
