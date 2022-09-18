#  midi2vjoy.py
#  
#  Copyright 2017  <c0redumb>
#  Copyright 2022  <tseardh>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import sys, os, time, traceback
import ctypes
from optparse import OptionParser
import pygame.midi
import winreg
import pynput

# Constants
# Axis mapping
axis = {'X': 0x30, 'Y': 0x31, 'Z': 0x32, 'RX': 0x33, 'RY': 0x34, 'RZ': 0x35,
        'SL0': 0x36, 'SL1': 0x37, 'WHL': 0x38, 'POV': 0x39}

# Globals
options = None
from pynput.keyboard import Key, Controller
keyboard = Controller()
functionKeys = {'F1': Key.f1, 'F2': Key.f2, 'F3': Key.f3, 'F4': Key.f4, 'F5': Key.f5, 
        'F6': Key.f6, 'F7': Key.f7, 'F8': Key.f8, 'F9': Key.f9, 'F10': Key.f10, 'F11': Key.f11, 'F12': Key.f12}

def midi_test():
    n = pygame.midi.get_count()

    # List all the devices and make a choice
    print('Input MIDI devices:')
    for i in range(n):
        info = pygame.midi.get_device_info(i)
        if info[2]:
            print(i, info[1].decode())
    d = int(input('Select MIDI device to test: '))
    
    # Open the device for testing
    try:
        print('Opening MIDI device:', d)
        m = pygame.midi.Input(d)
        print('Device opened for testing. Use ctrl-c to quit.')
        while True:
            while m.poll():
                print(m.read(1))
            time.sleep(0.1)
    except:
        m.close()

def getMidiInterface():
    n = pygame.midi.get_count()

    # List all the devices and make a choice
    print('Input MIDI devices:')
    for i in range(n):
        info = pygame.midi.get_device_info(i)
        if info[2]:
            print(i, info[1].decode())
    d = int(input('Select MIDI device to test: '))
    while d < 0 or d >= n:
        d = int(input('Select MIDI device to test: '))
    return d

        
def read_conf(conf_file):
    '''Read the configuration file'''
    table = {}
    vids = []
    with open(conf_file, 'r') as f:
        for l in f:
            if len(l.strip()) == 0 or l[0] == '#':
                continue
            fs = l.split()
            midiType = (str(fs[0])).upper()
            midiControl = (int(fs[1]))
            midiChannel = (int(fs[2]))

            if  midiType != 'NOTE' and midiType != 'CC':
                raise ValueError('Configuration file syntax incorrect: ' + l)

            val = parse_action(fs)

            if midiType == 'NOTE':
                # For notes we add both the note_on and note_off messages for all the channels specified (1 or all 16)
                if midiChannel == 0:
                    for i in range (1, 16):
                        key = (144 + i - 1, midiControl)        # midiTypes 144-159 are the NOTE_ON messages for channel 1 through 16
                        table[key] = val
                        key = (128 + i - 1, midiControl)         # midiTypes 144-159 are the NOTE_OFF messages for channel 1 through 16
                        table[key] = val
                else:
                    key = (144 + midiChannel - 1, midiControl)        # midiTypes 144-159 are the NOTE_ON messages for channel 1 through 16
                    table[key] = val
                    key = (128 + midiChannel - 1, midiControl)         # midiTypes 128-143 are the NOTE_OFF messages for channel 1 through 16
                    table[key] = val
            elif midiType == 'CC':
                if midiChannel == 0:
                    for i in range (1, 16):
                        key = (176 + i - 1, midiControl)        # midiTypes 176-191 are the CONTROL_CHANGE messages for channel 1 through 16
                        table[key] = val
                else:
                    key = (176 + midiChannel - 1, midiControl)        # midiTypes 176-191 are the CONTROL_CHANGE messages for channel 1 through 16
                    table[key] = val

            if val[0] in ['AXIS', 'BUTTON', 'TOGGLE']:
                vid = val[1]
                if not vid in vids:
                    vids.append(vid)
    return (table, vids)

def parse_action(fs):
    action = (str(fs[3])).upper()
    if action == 'KEY':
        keyboardkey = (str(fs[4])).lower()
        keyboardmodifiers = ''
        if len(fs) >= 6:
            keyboardmodifiers = (str(fs[5])).upper()
        if len(fs) >= 7:
            keyboardmodifiers = keyboardmodifiers + ' ' + (str(fs[6])).upper()
        if len(fs) >= 8:
            keyboardmodifiers = keyboardmodifiers + ' ' + (str(fs[7])).upper()
    
        return (action, keyboardkey, keyboardmodifiers)
    elif action == 'BUTTON':
        joyid = (int(fs[4]))
        buttonid = (int(fs[5]))
        if (str(fs[0])).upper() == 'CC':
            sensitivity = 4
            if len(fs) >= 7:
                sensitivity = (int(fs[6]))
            return (action, joyid, buttonid, sensitivity, 0)    # the 5th element is used to store the last position of the midicontrol where a buttonpress was executed
        else:
            return (action, joyid, buttonid)
    elif action == 'AXIS':
        joyid = (int(fs[4]))
        axisid = fs[5]
        if not axisid in axis:
            raise ValueError('Invalid axis in configuration file: ' + axisid)
        return (action, joyid, axisid)
    elif action == 'TOGGLE':
        joyid = (int(fs[4]))
        buttonid = (int(fs[5]))
        initstate = 0
        if len(fs) >= 7:
            initstate = (int(fs[6]))
        return (action, joyid, buttonid, initstate)
    elif action == "ROTARY":
        if (str(fs[0])).upper() != 'CC':
            raise ValueError('ROTARY only allowed with CC midi controls' + fs)
        joyid = (int(fs[4]))
        buttondownid = (int(fs[5]))
        buttonupid = (int(fs[6]))
        sensitivity = 4
        if len(fs) >= 8:
            sensitivity = (int(fs[7]))
        return (action, joyid, buttondownid, buttonupid, sensitivity, 0)    # the 5th element is used to store the last position of the midicontrol where a buttonpress was executed
    else:
        raise ValueError('Incorrect action in configuration file: ' + action)

def performKeyPress(kbKey, kbMods):
    if 'SHIFT' in kbMods:
        keyboard.press(Key.shift)
    if 'CTRL' in kbMods:
        keyboard.press(Key.ctrl)
    if 'ALT' in kbMods:
        keyboard.press(Key.alt)
    if kbKey.upper() in functionKeys:
        keyboard.press(functionKeys[kbKey.upper()])
    else:
        keyboard.press(kbKey)

def performKeyRelease(kbKey, kbMods):
    if kbKey.upper() in functionKeys:
        keyboard.release(functionKeys[kbKey.upper()])
    else:
        keyboard.release(kbKey)
    if 'SHIFT' in kbMods:
        keyboard.release(Key.shift)
    if 'CTRL' in kbMods:
        keyboard.release(Key.ctrl)
    if 'ALT' in kbMods:
        keyboard.release(Key.alt)

def isPressAction(miditype, midivalue):
    if 144 <= miditype <= 159:
        return True
    elif (176 <= miditype <= 191) and midivalue == 127:
        return True
    return False

def isMidiNote(miditype):
    return (128 <= miditype <= 159)

def isMidiCC(miditype):
    return (176 <= miditype <= 191)

def joystick_run():
    # Process the configuration file
    if options.conf == None:
        print('Must specify a configuration file')
        return
    try:
        if options.verbose:
            print('Opening configuration file:', options.conf)
        (table, vids) = read_conf(options.conf)
        #print(table)
        #print(vids)
    except:
        print('Error processing the configuration file:', options.conf)
        return
        
    # Getting the MIDI device ready
    if options.midi == None:
        print('Must specify a MIDI interface to use')
        return
    try:
        if options.verbose:
            print('Opening MIDI device:', options.midi)
        midi = pygame.midi.Input(options.midi)
    except:
        print('Error opening MIDI device:', options.midi)
        return
        
    # Load vJoysticks
    try:
        # Load the vJoy library
        # Load the registry to find out the install location
        vjoyregkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{8E31F76F-74C3-47F1-9550-E041EEDC5FBB}_is1')
        installpath = winreg.QueryValueEx(vjoyregkey, 'InstallLocation')
        winreg.CloseKey(vjoyregkey)
        #print(installpath[0])
        dll_file = os.path.join(installpath[0], 'x64', 'vJoyInterface.dll')
        vjoy = ctypes.WinDLL(dll_file)
        #print(vjoy.GetvJoyVersion())
        
        # Getting ready
        for vid in vids:
            if options.verbose:
                print('Acquiring vJoystick:', vid)
            assert(vjoy.AcquireVJD(vid) == 1)
            assert(vjoy.GetVJDStatus(vid) == 0)
            vjoy.ResetVJD(vid)
    except:
        #traceback.print_exc()
        print('Error initializing virtual joysticks')
        return
    
    try:
        if options.verbose:
            print('Ready. Use ctrl-c to quit.')
        while True:
            while midi.poll():
                ipt = midi.read(1)
                key = tuple(ipt[0][0][0:2])
                reading = ipt[0][0][2]

                # Check that the input is defined in table
                print(key, reading)
                if not key in table:
                    # key is not in the table, so no action required
                    continue

                opt = table[key]
                if options.verbose:
                    print(key, '->', opt, reading)

                if opt[0] == 'KEY':
                    if isPressAction(key[0], reading):
                        performKeyPress(opt[1], opt[2])
                    else:
                        performKeyRelease(opt[1], opt[2])
                    #continue

                elif opt[0] == 'AXIS':
                    if not opt[2] in axis:
                        continue
                    reading = (reading + 1) << 8
                    vjoy.SetAxis(reading, opt[1], axis[opt[2]])
                    #continue

                elif opt[0] == 'BUTTON':
                    if isMidiNote(key[0]):
                        if isPressAction(key[0], reading):
                            vjoy.SetBtn(reading, opt[1], int(opt[2]))
                        else:
                            vjoy.SetBtn(0, opt[1], int(opt[2]))
                    if isMidiCC(key[0]):
                        # This can be either a rotary/axis control or a button in CC mode
                        # A button in CC mode either has a value (reading) of 127 (pressed) or 0 (released)
                        # A rotary/axis control will have other values

                        if reading == 127 and opt[4] == 0:
                            vjoy.SetBtn(reading, opt[1], int(opt[2]))
                            newval = (opt[0], opt[1], opt[2], opt[3], 127)
                            table[key] = newval
                        elif reading == 0 and opt[4] == 127:
                            vjoy.SetBtn(0, opt[1], int(opt[2]))
                            newval = (opt[0], opt[1], opt[2], opt[3], 0)
                            table[key] = newval
                        else:
                            # this is a rotary/axis control. Only if enough of a change has occurred in the 
                            # position of the midi control a button press and release is simulated 
                            # A change in either direction initiates a button press (i.e. one button per 
                            # rotary control on the midi device)
                            if (opt[4] + opt[3] <= reading) or (reading + opt[3] <= opt[4]): 
                                vjoy.SetBtn(True, opt[1], int(opt[2]))
                                time.sleep(0.02) # 0.02 optimized for best responsiveness in xplane
                                vjoy.SetBtn(False, opt[1], int(opt[2]))
                                time.sleep(0.02)
                                # store the new reading in the table for the next round
                                newval = (opt[0], opt[1], opt[2], opt[3], int(reading))
                                table[key] = newval
                    
                elif opt[0] == 'TOGGLE':
                    if isPressAction(key[0], reading):
                        if opt[3]:
                            vjoy.SetBtn(0, opt[1], int(opt[2]))
                            newval = (opt[0], opt[1], opt[2], 0)
                        else:
                            vjoy.SetBtn(1, opt[1], int(opt[2]))
                            newval = (opt[0], opt[1], opt[2], 1)
                        table[key] = newval
                    
                elif opt[0] == 'ROTARY':
                    # initial implementation does not take sensitivity into account. Problem is that once the value
                    # reaches 0 or 127, the value remains that while the rotary continues to be turned in that direction
                    # Only when the direction is changed, does the value change again
                    if (reading <= opt[5] and opt[5]!=127):
                        # turning counterclockwise
                        vjoy.SetBtn(True, opt[1], int(opt[2]))
                        time.sleep(0.025) # 0.02 optimized for best responsiveness in xplane
                        vjoy.SetBtn(False, opt[1], int(opt[2]))
                        time.sleep(0.025) # 0.02 optimized for best responsiveness in xplane
                    elif (reading >= opt[5]):
                        # turning clockwise
                        vjoy.SetBtn(True, opt[1], int(opt[3]))
                        time.sleep(0.025) # 0.02 optimized for best responsiveness in xplane
                        vjoy.SetBtn(False, opt[1], int(opt[3]))
                        time.sleep(0.025) # 0.02 optimized for best responsiveness in xplane
                    # store the new reading in the table for the next round
                    newval = (opt[0], opt[1], opt[2], opt[3], opt[4], int(reading))
                    table[key] = newval

            time.sleep(0.1)  # sleep a while if no midi events are present to prevent unneccassary use of processor
    except:
        traceback.print_exc()
        pass
        
    # Relinquish vJoysticks
    for vid in vids:
        if options.verbose:
            print('Relinquishing vJoystick:', vid)
        vjoy.RelinquishVJD(vid)
    
    # Close MIDI device
    if options.verbose:
        print('Closing MIDI device')
    midi.close()
        
def main():
    # parse arguments
    parser = OptionParser()
    parser.add_option("-t", "--test", dest="runtest", action="store_true",
                      help="To test the midi inputs")
    parser.add_option("-m", "--midi", dest="midi", action="store", type="int",
                      help="File holding the list of file to be checked")
    parser.add_option("-c", "--conf", dest="conf", action="store",
                      help="Configuration file for the translation")
    parser.add_option("-v", "--verbose",
                          action="store_true", dest="verbose")
    parser.add_option("-q", "--quiet",
                          action="store_false", dest="verbose")
    global options
    (options, args) = parser.parse_args()
    
    pygame.midi.init()
    
    if options.runtest:
        midi_test()
    elif options.midi == None:
        options.midi = getMidiInterface()
        joystick_run()
    else:
        joystick_run()
    
    pygame.midi.quit()

if __name__ == '__main__':
    main()
