import argparse
import json
try:
  import yaml
except:
  print("Try: pip install pyyaml")

from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadDecoder

parser = argparse.ArgumentParser()

parser.add_argument('--host', help="SAJ Inverter IP",
                    type=str, default='192.168.0.32', required=False)
parser.add_argument('--port', help="SAJ Inverter Port",
                    type=int, default=502, required=False)

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


#print(modbus)
sensors = modbus[0]['sensors']

address = 36608  # First register with Inverter details.
count = 29  # Read this amount of registers
connected = False
client = ModbusTcpClient(host=args.host, port=args.port, timeout=3)
client.connect()

try:
    inverter_data = client.read_holding_registers(
        unit=1, address=address, count=count)
    connected = True
except ConnectionException as ex:
    print(f'Connecting to device {args.host} failed!')
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
        print(json_data)

sensor_by_addr = {}
for sensor in sensors:
    address = sensor['address']
    sensor_by_addr[address] = sensor

adresses = list(sensor_by_addr.keys())
adresses.sort()
print("adress:", adresses[0],"to", adresses[-1])
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

#print('chunks:')
#for c in adress_chunks:
#    print(c)

print("Fetching chunks")
data = {}

for chunk in adress_chunks:
    address = chunk['start']
    count = chunk['count']
    connected = False
    print('chunk', chunk)

    try:
        inverter_data = client.read_holding_registers(
            unit=1, address=address, count=count)
        connected = True
    except ConnectionException as ex:
        print(f'Connecting to device {args.host} failed!')
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
            
                print(sensor['name'], value, )
                address += sensor['count']

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
        print(f'Connecting to device {args.host} failed!')
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

client.close()
print("##########################")
#for d in data:
#  print(d, data[d], data1[d])
