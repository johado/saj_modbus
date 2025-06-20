import argparse
import json
from datetime import datetime
import time
import sys
import struct
try:
  import yaml
#  from pyyaml import yaml
except Exception as exc:
  print("Try: pip3 install pyyaml", exc)
  exit(1)

try:  
  from pymodbus.client.sync import ModbusTcpClient
  from pymodbus.constants import Endian
  from pymodbus.exceptions import ConnectionException
  from pymodbus.payload import BinaryPayloadDecoder
except Exception as exc:
  print("Try: pip3 install pymodbus", exc)
  exit(1)

read_info = False
chunk_min_range = 16
chunk_max_count = 100 # Snooping indicates a lot of read with 0x50 = 80
chunk_extra_range = 0

exclude_class = ['schedule']
include_class = []  # All
print_values = False
print_values2 = False
print_hex = False
#print_values = True
print_csv = True
prev_csvheader = ''
read_num_lines = int(24*60*60 / 10)

parser = argparse.ArgumentParser()

parser.add_argument('--host', help="SAJ Inverter IP",
                    type=str, default='192.168.0.32', required=False)
parser.add_argument('--port', help="SAJ Inverter Port",
                    type=int, default=502, required=False)
parser.add_argument('--readcsv', help="Read theese many csv lines",
                    type=int, default=read_num_lines, required=False)
parser.add_argument('--list', action='store_true', help="Read sensors",
                    default=False, required=False)
parser.add_argument('--include',  help="classes to include",
                    type=str, default=None, required=False)
parser.add_argument('--exclude',  help="classes to exclude",
                    type=str, default='schedule', required=False)


parser.add_argument('--read', help="Read register(s) (reg1,reg2)",
                    type=str, default='', required=False)
parser.add_argument('--write', help="Write register(s) (reg=value,regs=value)",
                    type=str, default='', required=False)
parser.add_argument('--hex', action='store_true', help="Print hex value when listing/reading sensors",
                    default=False, required=False)


args = parser.parse_args()

modbus = False
with open("modbus.yaml", "r") as stream:
    try:
        modbus = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

#with open("configuration1.yaml", "r") as stream:
#    try:
#        modbus = yaml.safe_load(stream)
#    except yaml.YAMLError as exc:
#        print(exc)
print_hex = args.hex
if args.include is not None:
    include_class = args.include.split(',')
exclude_class = args.exclude.split(',')
read_reg = args.read
write_reg = args.write
if read_reg != '' or write_reg != '':
    read_num_lines = 0
else:
    read_num_lines = args.readcsv
if args.list:
    print_csv = False
    print_values = True
    read_num_lines = 1
#print(modbus)
sensors = modbus[0]['sensors']
#for s in sensors:
#    print(s['name'], s['address'])

sensor_by_addr = {}
sensor_by_name = {}
sensor_classes = {}
for sensor in sensors:
    address = sensor['address']
    sensor_by_addr[address] = sensor
    sensor_by_name[sensor['name']] = sensor
    if not ('device_class' in sensor):
        sensor['device_class'] = ''
    if 'device_class' in sensor:
        sensor_classes[sensor['device_class']] = sensor['device_class']

if len(include_class) == 0:
    include_class = list(sensor_classes.keys())
    include_class = [item for item in sensor_classes if item not in exclude_class ]

#print('include:', include_class)

connected = False
client = ModbusTcpClient(host=args.host, port=args.port, timeout=3)
client.connect()

def read_regs(client):
    global sensors
    global adress_chunks
    global connected
    #print("Fetching chunks")
    data = {}

    for chunk in adress_chunks:
        address = chunk['start']
        count = chunk['count']
        connected = False
        #print('chunk', chunk)

        try:
            inverter_data = client.read_holding_registers(
                unit=1, address=address, count=count)
            connected = True
        except ConnectionException as ex:
            print("Connecting to device %s failed!" % (args.host))
            connected = False

        if connected:
            if not inverter_data.isError():
                decoder = BinaryPayloadDecoder.fromRegisters(
                    inverter_data.registers, byteorder=Endian.Big)

                while address < chunk['start'] + chunk['count']:
                    if address in sensor_by_addr:
                        sensor = sensor_by_addr[address]
                    else:
                        sensor = {'address': address, 
                                'name': 'dummy'+str(address),
                                'count' : 1,
                                'data_type': 'uint16',
                                'scale': 1,
                                'precision': 0 }
                    #print(sensor)                    
                    scale = sensor['scale']
                    precision = sensor['precision']
                    if scale == 0:
                        scale = 1
                    divideprecision = precision
                    while divideprecision > 0:
                        scale /= 10
                        divideprecision -= 1
                        
                    if sensor['data_type'] == 'uint16':
                        rawvalue = int(decoder.decode_16bit_uint())
                        data[sensor['name']] = str(round(rawvalue * scale, precision))
                    elif sensor['data_type'] == 'int16':
                        rawvalue = decoder.decode_16bit_int()
                        data[sensor['name']] = str(round(rawvalue * scale, precision))
                    elif sensor['data_type'] == 'uint32':
                        rawvalue = decoder.decode_32bit_uint()
                        data[sensor['name']] = str(round(rawvalue * scale, precision))
                    elif sensor['data_type'] == 'int32':
                        rawvalue = decoder.decode_32bit_int()
                        data[sensor['name']] = str(round(rawvalue * scale, precision))
                    else:
                        print("data_type: ", sensor['data_type'], "not handled")
                        rawvalue = 0xABADC0DE

                    value = data[sensor['name']]
                    if sensor['count'] == 1:
                        hexvalue = "0x%04X" % (rawvalue)
                    elif sensor['count'] == 2:
                        hexvalue = "0x%08X" % (rawvalue)
                    else:
                        hexvalue ='?'
                    unit = sensor['unit_of_measurement'] if 'unit_of_measurement' in sensor else ''
                    if unit == '0xHHMM':
                        value = int(value)
                        value = "%02i:%02i" % ( value / 256, value & 255)
                        unit = ''
                    elif unit == '0xDFPC':  # DayFlag and 100xPower
                        value = int(value)
                        value = "%02x %i W" % ( int(value / 256), (value & 255) * 100)
                        unit = ''
                    elif unit == '0xYYYYMMDD':
                        value = int(value)
                        value = "%04i-%02i-%02i" % ( int(value >> 16), ((value >> 8) & 255), value & 0xFF)
                        unit = ''                    
                    elif unit == '0xHHMMSSxx':
                        value = int(value)
                        value = "%02i:%02i:%02i.%03i" % ( (value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 255, value & 0xFF)
                        unit = ''
                    data[sensor['name']] = { 'v': value, 'u':unit, 'h': hexvalue}
                    
                    if print_values2:
                        print(sensor['name'], value, unit)
                    address += sensor['count']
    return data

linenbr = 0
def print_data(data):
    global linenbr
    global prev_csvheader
    units = ['W', 'V', 'A', 'kWh']
    sensor_by_unit = {}
    for u in units:
        if not (u in sensor_by_unit):
            sensor_by_unit[u] = []

    for sensor in sensors:
        u = sensor['unit_of_measurement'] if 'unit_of_measurement' in sensor else ''
        if not (u in sensor_by_unit):
            sensor_by_unit[u] = []
        sensor_by_unit[u].append(sensor['name'])

    #for u in sensor_by_unit:
    #    print(u, sensor_by_unit[u])

    orderby = 'unit'
    #orderby = 'name'

    csvheader = 'DateTime;'
    csvvalue = data['DateTime']['v']+';'
    if orderby == 'unit':
        for u in sensor_by_unit:
            names = sensor_by_unit[u]
            names.sort()
            for name in names:
                sensor = sensor_by_name[name]
                if name in data:
                    value = data[name]['v']
                    unit = data[name]['u']
                    
                    if 'device_class' in sensor and sensor['device_class'] in include_class:
                        if print_values:
                            if print_hex:
                                print(sensor['name'], value, unit, data[name]['h'])
                            else:
                                print(sensor['name'], value, unit)
                        if unit != '':
                            csvheader += name + '['+unit+'];'
                        else:
                            csvheader += name + ';'
                        csvvalue += value + ';'
                else:
                    if not print_csv:
                        print(name, ' not in data?')
    elif orderby == 'name':
        names = list(sensor_by_name.keys())
        names.sort()
        for name in names:
            sensor = sensor_by_name[name]
            if name in data:
                value = data[name]['v']
                unit = data[name]['u']

                if not ('device_class' in sensor) or 'device_class' in sensor and sensor['device_class'] in include_class:
                #if sensor['device_class'] in include_class:
                    if print_values:
                            if print_hex:
                                print(sensor['name'], value, unit, data[name]['h'])
                            else:
                                print(sensor['name'], value, unit)
                    if unit != '':
                        csvheader += name + '['+unit+'];'
                    else:
                        csvheader += name + ';'
                    csvvalue += value + ';'
            else:
                if not print_csv:
                    print(name, ' not in data?')
    if print_csv:
        # Sometimes som values are missing, if so, resync CSV header
        if linenbr == 0 or csvheader != prev_csvheader:
            print(csvheader)
            prev_csvheader = csvheader
        print(csvvalue)
    linenbr += 1

"""
data1 = data.copy()

data = {}
print("Fetching each sensor")
for sensor in sensors:
    address = sensor['address']
    count = sensor['count']
    connected = False
    #print(sensor)
    try:
        inverter_data = client.read_holding_registers(
            unit=1, address=address, count=count)
        connected = True
    except ConnectionException as ex:
        print('Connecting to device %s failed!' % (args.host))
        connected = False

    if connected:
        if not inverter_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                inverter_data.registers, byteorder=Endian.Big)

            scale = sensor['scale']
            precision = sensor['precision']
            if scale == 0:
                scale = 1
            while precision > 0:
                scale /= 10
                precision -= 1
                
            if sensor['data_type'] == 'uint16':
                data[sensor['name']] = str(decoder.decode_16bit_uint() * scale)
            elif sensor['data_type'] == 'int16':
                data[sensor['name']] = str(decoder.decode_16bit_int() * scale)
            elif sensor['data_type'] == 'uint32':
                data[sensor['name']] = str(decoder.decode_32bit_uint() * scale)
            elif sensor['data_type'] == 'int32':
                data[sensor['name']] = str(decoder.decode_32bit_int() * scale)
            else:
                print("data_type: ", sensor['data_type'], "not handled")

            print(sensor['name'], data[sensor['name']], sensor['unit_of_measurement'] if 'unit_of_measurement' in sensor else '')
"""


if read_info:
    address = 36608  # First register with Inverter details.
    count = 29  # Read this amount of registers

    try:
        inverter_data = client.read_holding_registers(
            unit=1, address=address, count=count)
        connected = True
    except ConnectionException as ex:
        print('Connecting to device %s failed!' % (args.host))
        connected = False

    if connected:
        if not inverter_data.isError():
            decoder = BinaryPayloadDecoder.fromRegisters(
                inverter_data.registers, byteorder=Endian.Big)

            data = {}

            data["devicetype"] = str(decoder.decode_16bit_uint())
            data["subtype"] = str(decoder.decode_16bit_uint())
            data["commver"] = str(round(decoder.decode_16bit_uint() * 0.001, 3))
            data["serialnumber"] = str(decoder.decode_string(20).decode('ascii'))
            data["procuctcode"] = str(decoder.decode_string(20).decode('ascii'))
            data["dispswver"] = str(round(decoder.decode_16bit_uint() * 0.001, 3))
            data["masterctrlver"] = str(
                round(decoder.decode_16bit_uint() * 0.001, 3))
            data["slavecrtlver"] = str(
                round(decoder.decode_16bit_uint() * 0.001, 3))
            data["disphwver"] = str(round(decoder.decode_16bit_uint() * 0.001, 3))
            data["crtlhwver"] = str(round(decoder.decode_16bit_uint() * 0.001, 3))
            data["powerhwver"] = str(round(decoder.decode_16bit_uint() * 0.001, 3))

            json_data = json.dumps(data)
            #print(json_data)


adresses = list(sensor_by_addr.keys())
adresses.sort()
#print("Addresses:", adresses)
#print("adress:", adresses[0],"to", adresses[-1])
adress_chunks = []
chunk = {}
chunk['start'] = adresses[0]
chunk['count'] = sensor_by_addr[adresses[0]]['count']
for a in adresses:
    sensor = sensor_by_addr[a]
    if (sensor['address']+sensor['count']) - (chunk['start'] + chunk['count']) < chunk_min_range:
        # increase chunk
        chunk['count'] = sensor['address']+sensor['count'] - chunk['start']
    else:
        # new chunk
        adress_chunks.append(chunk.copy())
        chunk['start'] = sensor['address']
        chunk['count'] = sensor['count']

    chunk['count'] += chunk_extra_range
    while chunk['count'] > chunk_max_count:
        nextchunk = { 'start': chunk['start'] + chunk_max_count, 'count': chunk['count'] - chunk_max_count }
        chunk['count'] = chunk_max_count
        adress_chunks.append(chunk.copy())
        chunk = nextchunk
adress_chunks.append(chunk.copy())

#print('chunks:')
#for c in adress_chunks:
#    print(c)

linenbr = 0
prevday = ''
while linenbr < read_num_lines:
    dt = datetime.now()
    today = dt.strftime("%Y%m%d")
    datetimestr = dt.strftime("%Y-%m-%d %H:%M:%S")
    data = read_regs(client)
    if not connected:
        sys.stdout.flush()
        time.sleep(2)
        exit(1)

    data['DateTime'] = { 'v': datetimestr, 'u':''}

    if prevday != today:
        # New day - start with header
        linenbr = 0
        if prevday != '':
          # Exit to get a new file from systemd
          exit(0)
        prevday = today        
    print_data(data)
    if linenbr < read_num_lines:
        if linenbr % 10 == 0:
            sys.stdout.flush()
        time.sleep(8)

if read_reg != '':
        regs = read_reg.split(',')
        for reg in regs:
            if reg in sensor_by_name:
                sensor = sensor_by_name[reg]
            else:
                print("# Register",reg,"not found, try as number")
                sensor = {'address' : int(reg, 0), 'count': 1 }

            chunk = {}
            chunk['start'] = sensor['address']
            chunk['count'] = sensor['count']
            adress_chunks = [chunk]
            data = read_regs(client)
            for k in data:
                if print_hex:
                    print(k, data[k]['v'], data[k]['u'], data[k]['h'])
                else:
                    print(k, data[k]['v'], data[k]['u'])


if write_reg != '':
        regs = write_reg.split(',')
        for reg_value in regs:
            [reg, value]=reg_value.split('=')
            if reg in sensor_by_name:
                sensor = sensor_by_name[reg]
                value=int(value, base=0)
                s = "Write to %s %i 0x%04x: %i 0x%08x" % ( reg, sensor['address'], sensor['address'], value, value)
                print(s, sensor)
                if sensor['data_type'] == 'uint32':
                    #from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
                    #builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                    #builder.add_32bit_uint(value)
                    #payload = builder.build()
                    #payload = struct.pack('>I', value)
                    #print('payload', payload)
                    print('payload: 0x%08X' % ( value))
                    #res = client.write_register(address = sensor['address'],value = payload, count=2,unit= 1,skip_encode = True)
                    res = client.write_registers(address = sensor['address'],
                                                 #values = [ struct.pack('>H', (value >> 16) & 0xFFFF), struct.pack('>H', value & 0xFFFF)],
                                                 values = [ (value >> 16) & 0xFFFF, value & 0xFFFF],
                                                 count=2,unit= 1, skip_encode = False)
                else:
                    res =client.write_register(address = sensor['address'], value=value, count=sensor['count'], unit = 1)
                print(res)
                #for k in data:
                #    print(k, data[k]['v'], data[k]['u'])


client.close()
#print("##########################")
#for d in data:
#  print(d, data[d], data1[d])
