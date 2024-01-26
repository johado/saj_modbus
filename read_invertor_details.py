import argparse
import json
from datetime import datetime
import time

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

exclude_class = ['schedule']
print_values = False
#print_values = True
print_csv = True
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
parser.add_argument('--read', help="Read register(s) (reg1,reg2)",
                    type=str, default='', required=False)
parser.add_argument('--write', help="Write register(s) (reg=value,regs=value)",
                    type=str, default='', required=False)


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

connected = False
client = ModbusTcpClient(host=args.host, port=args.port, timeout=3)
client.connect()

def read_regs(client):
    global sensors
    global adress_chunks
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
                        data[sensor['name']] = str(round(decoder.decode_16bit_uint() * scale, precision))
                    elif sensor['data_type'] == 'int16':
                        data[sensor['name']] = str(round(decoder.decode_16bit_int() * scale, precision))
                    elif sensor['data_type'] == 'uint32':
                        data[sensor['name']] = str(round(decoder.decode_32bit_uint() * scale, precision))
                    elif sensor['data_type'] == 'int32':
                        data[sensor['name']] = str(round(decoder.decode_32bit_int() * scale, precision))
                    else:
                        print("data_type: ", sensor['data_type'], "not handled")

                    value = data[sensor['name']]
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
                    data[sensor['name']] = { 'v': value, 'u':unit}
                
                    #print(sensor['name'], value, unit)
                    address += sensor['count']
    return data

linenbr = 0
def print_data(data):
    global linenbr
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
                    
                    if not ('device_class' in sensor and sensor['device_class'] in exclude_class):
                        if print_values:
                            print(sensor['name'], value, unit) 
                        if unit != '':
                            csvheader += name + '['+unit+'];'
                        else:
                            csvheader += name + ';'
                        csvvalue += value + ';'
                else:
                    print(name, ' not in data?')
    elif orderby == 'name':
        names = list(sensor_by_name.keys())
        names.sort()
        for name in names:
            sensor = sensor_by_name[name]
            if name in data:
                value = data[name]['v']
                unit = data[name]['u']

                if not (sensor['device_class'] in exclude_class):
                    if print_values:                
                        print(sensor['name'], value, unit)                
                    if unit != '':
                        csvheader += name + '['+unit+'];'
                    else:
                        csvheader += name + ';'
                    csvvalue += value + ';'
            else:
                print(name, ' not in data?')
    if print_csv:
        if linenbr == 0:
            print(csvheader)
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

sensor_by_addr = {}
sensor_by_name = {}
for sensor in sensors:
    address = sensor['address']
    sensor_by_addr[address] = sensor
    sensor_by_name[sensor['name']] = sensor

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
  if (sensor['address']+sensor['count']) - (chunk['start'] + chunk['count']) < 16:
      # increase chunk
      chunk['count'] = sensor['address']+sensor['count'] - chunk['start']
  else:
      # new chunk
      adress_chunks.append(chunk.copy())
      chunk['start'] = sensor['address']
      chunk['count'] = sensor['count']
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
    data['DateTime'] = { 'v': datetimestr, 'u':''}

    if prevday != today:
        # New day - start with header
        linenbr = 0
        prevday = today        
    print_data(data)
    if linenbr < read_num_lines:
        time.sleep(8)

if read_reg != '':
        regs = read_reg.split(',')
        for reg in regs:
            if reg in sensor_by_name:
                sensor = sensor_by_name[reg]
                chunk = {}
                chunk['start'] = sensor['address']
                chunk['count'] = sensor['count']
                adress_chunks = [chunk]
                data = read_regs(client)
                for k in data:
                    print(k, data[k]['v'], data[k]['u'])
            else:
                print("# Register",reg,"not found")

if write_reg != '':
        regs = write_reg.split(',')
        for reg_value in regs:
            [reg, value]=reg_value.split('=')
            if reg in sensor_by_name:
                sensor = sensor_by_name[reg]
                value=int(value, base=0)
                print("Write to", reg, value, sensor)
                res =client.write_register(address = sensor['address'], value=value, unit = 1)
                print(res)
                #for k in data:
                #    print(k, data[k]['v'], data[k]['u'])


client.close()
#print("##########################")
#for d in data:
#  print(d, data[d], data1[d])
