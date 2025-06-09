#!/bin/env python3
# Usage: python3 getspot.py --plotprice --price 2025-05-30:2025-05-31 --area SE4 --calc

import argparse
import datetime
try:
  import requests
except:
    print("Try pip install requests");
    exit(1)

import json
import os
import subprocess
import math

vin = os.environ.get('TESLA_VIN')
car_total_kWh = 78
car_target_SOC = 85
car_SOC = 30
car_current = 13 # Most likely current (on the low side)
car_charge_current_candidates = [8,9,10, 11,12,13,14,15]

bat_total_kWh = 15.36
bat_target_SOC = 100
bat_SOC = 20
bat_power = 3000
bat_power_high = 7000
bat_max_power_by_hour = {0: bat_power, 1: bat_power, 2:bat_power, 3: bat_power,
                         4: bat_power, 5:bat_power, 6: bat_power, 7:bat_power,
                         8: bat_power, 9:bat_power, 10: bat_power_high, 11:bat_power_high,
                         12: bat_power_high, 13:bat_power_high, 14: bat_power_high, 15:bat_power_high,
                         16: bat_power, 17: bat_power, 18:bat_power, 19: bat_power,
                         20:bat_power,  21: bat_power, 22:bat_power, 23: bat_power
                         }
bat_charge_power_candidates = [2000, 3000, 4000, 5000, 6000]
bat_charge_power_candidates2 = [2000, 3000, 4000, 5000, 6000, 7000]



def spot2cost(spot):
    ## (spotprice+addon+transfer+tax)*VAT
    # New pricing from 2024: transfer = (16+0.0561*spot)*1,25
    # tax = 42,8*1,25
    #2023: return [ cost, (cost+3.2+20.4+39.2)*1.25 ]
    return round((spot+3.2+16+0.0561*spot+42.8)*1.25,3)

def spot2costinfo(spot, dt):
    ## (spotprice+addon+transfer+tax)*VAT
    # New pricing from 2024: transfer = (16+0.0561*spot)*1,25
    # tax = 42,8*1,25
    #2023: return [ cost, (cost+3.2+20.4+39.2)*1.25 ]
    return {'dt': dt, 'spot': spot, 'cost': round((spot+3.2+16+0.0561*spot+42.8)*1.25,3), 'sell': round((spot+10+60),3)}



#curl -k --header 'Referer: https://www.vattenfall.se/elavtal/elpriser/timpris/' --header 'User-Agent: Mozilla/5.0' -v https://www.vattenfall.se/api/price/spot/pricearea/2024-01-15/2024-01-16/SN4

#{"data":{"resolution":"hourly","from":"2024-01-17T00:00:00","to":"2024-01-17T23:00:00","spotPrices":{"SE1":[{"dateTime":"2024-01-17T00:00:00","value":0.79264},
def getspot2(daydelta = 0, area = 'SE4'):
    area = area[0]+'E'+area[2:] # SNx vs SEx
    dt = datetime.datetime.now()
    dt = dt + datetime.timedelta(days=daydelta)    
    today = dt.strftime("%Y-%m-%d")
    
    #dtomorrow = dt + datetime.timedelta(days=1)
    #tomorrow = dtomorrow.strftime("%Y-%m-%d")
    # https://www.fortum.se/api/v1/spot_prices_month?date=2024-01-01
    url = "https://www.fortum.se/api/v1/spot_prices_hour?date="+today
    response = requests.get(url, headers=None, params=None)
    if response.status_code == 200 and response.content != '':
        try:
            with open(today+'_fortum.json', "w") as fp:
                fp.write(response.content.decode('utf-8'))

            spotprice = json.loads(response.content.decode('utf-8'))
            spotprice = spotprice['data']['spotPrices'][area]
        except Exception as e:
            print(e)
            spotprice = []
    else:
        #print(response)
        spotprice = []

    i = 0
    # Convert to vattenfall format
    for s in spotprice:
        spotprice[i] = spot2costinfo(s['value'] * 100, s['dateTime']) #{ 'dt': s["dateTime"], 'spot': s['value'] * 100, 'cost':spot2cost(s['value'] * 100)}
        i += 1

    #print(spotprice)
    """
    url = "https://www.fortum.se/api/v1/spot_prices_hour?date="+tomorrow
    response = requests.get(url, headers=None, params=None)
    spotprice = json.loads(response.content)
    spotprice = spotprice['data']['spotPrices']['SE4']
    print(spotprice)
    """
    return spotprice

#vattenfall:
#[{"TimeStamp":"2024-01-17T00:00:00","TimeStampDay":"2024-01-17","TimeStampHour":"00:00","Value":79.26,"PriceArea":"SN4","Unit":"re/kWh"},
def getspot(daydelta = 0, days=0, startdate = '', enddate = '', area = 'SN4'):
    area = area[0]+'N'+area[2:] # SNx vs SEx
    dt = datetime.datetime.now()
    dt = dt + datetime.timedelta(days=daydelta)
    if startdate != '':
        today = startdate
        dt = datetime.datetime.fromisoformat(today)
    else:
        today = dt.strftime("%Y-%m-%d")
    
    if enddate != '':
        tomorrow = enddate
    else:
        dtomorrow = dt + datetime.timedelta(days=days)
        tomorrow = dtomorrow.strftime("%Y-%m-%d")

    headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.vattenfall.se/elavtal/elpriser/timpris/"
    }
    url = "https://www.vattenfall.se/api/price/spot/pricearea/"+today+"/"+tomorrow+"/"+area # tomorrow
    #print("url:",url)
    try:
        response = requests.get(url, headers=headers, params=None)
        #print(response)
        if response.status_code == 200 and response.content != '':
            try:
                spotprice = json.loads(response.content.decode('utf-8'))
                with open(today+'_vattenfall.json', "w") as fp:
                    fp.write(response.content.decode('utf-8'))
            except Exception as e:
                print(e)
                spotprice = []
        else:
            #print(response)
            spotprice = []
            with open(today+'_vattenfall.json', "r") as fp:
                spotprice = json.loads(fp.read())
    except Exception as e:
        spotprice = []
        with open(today+'_vattenfall.json', "r") as fp:
            spotprice = json.loads(fp.read())


    i = 0
    # Trim down
    for s in spotprice:
        spotprice[i] =  spot2costinfo( s['Value'], s['TimeStamp']) #{ 'dt': s["TimeStamp"], 'spot': s['Value'], 'cost':spot2cost(s['Value'])}
        i += 1
    #print('delta', daydelta, spotprice)
    return spotprice

def set_charge_time(newtime):
    newtime = newtime.split(':')
    minutes = int(newtime[0])*60 + int(newtime[1])
    print('minutes:', str(minutes))
    cmd = ["/home/pi/go/bin/tesla-control",
           "-key-file", "/home/pi/tesla/privatekey.pem",
           "-ble",
           "-vin", vin,
           "charging-schedule", str(minutes)]
    print("Running", cmd)
    res = subprocess.run(cmd, stdin=subprocess.PIPE)
    print(res.stdout)    

def send_saj_commands(cmdstr):
    print('saj: cmdstr:', cmdstr)
    cmd = ["python3", "/home/pi/saj_modbus/read_invertor_details.py",
           "--write", cmdstr,
          ]
    print("Running", cmd)
    res = subprocess.run(cmd, stdin=subprocess.PIPE, cwd='/home/pi/saj_modbus')
    print(res.stdout)    




def car_charge_time_candidates(spotpricein, starttime = '18:00', endtime='06:00'):
    #print('## car_charge in:')
    #for s in spotpricein:
    #    print(s)

    _spotprice = []
    foundstart = False
    for s in spotpricein:
        #hhmm = s['TimeStamp'][11:16]
        #if not foundstart and hhmm < starttime and hhmm <= '23:00':
        #    print('Skipping', hhmm, s['TimeStamp'])
        #    continue
        #elif hhmm == starttime or hhmm == '00:00':
        #    foundstart = True
        #print("hhmm vs endtime", hhmm, endtime, foundstart)            
        #if foundstart and hhmm == endtime:
        #    break
        _spotprice.append(s)
    #print('## Filtered start:')
    #for s in spotprice:
    #    print(s)
        
    mincandidates = {}
    maxcandidates = {}
    #minrange = {0: 10000, _spotprice[0]['rangeavg'].copy()
    minrange = {}
    for r in range(1,8):
        minrange[r] = 10000
    maxrange = {}
    for r in range(1,8):
        maxrange[r] = -10000

    #maxrange = _spotprice[0]['rangeavg'].copy()
    # First find the minimum cost for various ranges
    for s in _spotprice:
        # 0123456789012345678
        # YYYY-MM-DDTHH:MM:SS
        hhmm = s['dt'][11:16]
#        if hhmm < starttime:
#            continue
        for r in s['rangeavg']:
            #print('r', r, minrange[r])
            if minrange[r] > s['rangeavg'][r]:
                minrange[r] = s['rangeavg'][r]
                mincandidates[r]={'dt': s['dt'], 'rangeavg': s['rangeavg'][r]}
            if maxrange[r] < s['rangeavg'][r]:
                maxrange[r] = s['rangeavg'][r]
                maxcandidates[r]={'dt': s['dt'], 'rangeavg': s['rangeavg'][r]}

    #print('minrange', minrange)
    #for c in mincandidates:
    #    print(c, mincandidates[c])
    #print('maxrange', maxrange)
    #for c in maxcandidates:
    #    print(c, maxcandidates[c])
    return mincandidates
# end car_charge_time

diffbin = 25
spotbin = 25
area = 'SE4'

def spot_statistics(spotprice):
    startday = spotprice[0]["dt"][0:10]
    endday  = spotprice[-1]["dt"][0:10]
    stat = {}
    stat['dayly'] = {}
    stat['weekly'] = {}
    stat['monthly'] = {}
    day = 1
    for s in spotprice:
        [date, time] = s['dt'].split('T')
        price = s['spot']
        if not date in stat['dayly']:
            stat['dayly'][date] = {}
            stat['dayly'][date] = {'avg':0, 'diff': 0, 'min':price, 'max':price,'sum':0,'cnt':0}
        stat['dayly'][date]['sum'] += price
        stat['dayly'][date]['cnt'] += 1
        stat['dayly'][date]['avg'] = round(stat['dayly'][date]['sum'] / stat['dayly'][date]['cnt'], 2)

        stat['dayly'][date]['min'] = min(price, stat['dayly'][date]['min'])
        stat['dayly'][date]['max'] = max(price, stat['dayly'][date]['max'])
        stat['dayly'][date]['diff'] = stat['dayly'][date]['max'] - stat['dayly'][date]['min']
        
        #print(s)
    stat['daylybin'] = {'avg':{},'diff':{}}
    avgsum = 0
    avgcnt = 0
    diffsum = 0
    avgcnt = 0
    dmax = 0
    dmin = 10000
    for date in stat['dayly']:
        d = stat['dayly'][date]
        avgsum += d['avg']
        diffsum += d['diff']
        avgcnt += 1
        dmax = max(dmax, d['max'])
        dmin = min(dmax, d['min'])
        abin = round(d['avg']/spotbin)*spotbin
        if not abin in stat['daylybin']['avg']:
            stat['daylybin']['avg'][abin] = {'cnt': 1, 'avgsum': d['avg']}
            #stat['daylybin']['avg'][abin] = 1
        else:
            stat['daylybin']['avg'][abin]['cnt'] += 1
            stat['daylybin']['avg'][abin]['avgsum'] += d['avg']
        dbin = round(d['diff']/diffbin)*diffbin
        if not dbin in stat['daylybin']['diff']:
            stat['daylybin']['diff'][dbin] = {'cnt': 1, 'diffsum': d['diff']}
            #stat['daylybin']['diff'][dbin] = 1
        else:
            stat['daylybin']['diff'][dbin]['cnt'] += 1
            stat['daylybin']['diff'][dbin]['diffsum'] += d['diff']

        #print(date, stat['dayly'][date])
    stat['priceavg'] = round(avgsum / avgcnt)
    stat['diffavg'] = round(diffsum / avgcnt)
    stat['min'] = dmin
    stat['max'] = dmax

    numkeys = len(stat['dayly'])
    diffkeys = stat['daylybin']['diff'].keys()
    diffvals = stat['daylybin']['diff'].values()
    maxdiff = max(diffkeys)
    #maxvals = max(diffvals)
    print(numkeys,'keys, max diff:', maxdiff)
    print("Spotprisskillnad max-min per dag från", startday,'till', endday, 'i', area,'diffavg', stat['diffavg'])
    print('diff antal %  värde[kr](diffsumma)')    
    b = 0
    vsum = 0
    vprodsum = 0
    while b <= maxdiff:
        if b in stat['daylybin']['diff']:
            v = stat['daylybin']['diff'][b]['cnt']
            vprodsum += stat['daylybin']['diff'][b]['diffsum']
        else:
            v = 0
        vsum += v
        
        print("%3i %3i %3i%% %6.2f" % (b, v, round(vsum*100/numkeys), vprodsum/100), "%.*s" % (int(v), '##########################################################################################################'))
        b += diffbin
    print('Genomsnittlig möjlig vinst vid arbitrage: %0.2f kr/dag per kWh, med 25%% moms: %0.2f kr/dag per kWh' % (vprodsum/100/numkeys, 1.25*vprodsum/100/numkeys))

#    for b in stat['daylybin']['diff']:
#        print(b, stat['daylybin']['diff'][b])
    avgkeys = stat['daylybin']['avg'].keys()
    avgvals = stat['daylybin']['avg'].values()
    maxavg = max(avgkeys)
    #maxvals = max(avgvals)
    print(numkeys,'keys, max avg:', maxavg)
    print("Spotprisfördelning medel/dag från", startday,'till', endday, 'i', area, 'avg', stat['priceavg'], 'min', stat['min'],'max', stat['max'])
    print('avg  antal')
    b = 0
    vsum = 0
    while b <= maxavg:
        if b in stat['daylybin']['avg']:
            v = stat['daylybin']['avg'][b]['cnt']
        else:
            v = 0
        vsum += v
        print("%4i %3i %3i%%" % (b, vsum, round(vsum*100/numkeys)), "%.*s" % (int(v), '#######################################################################################################'))
        b += spotbin
        
#    for b in stat['daylybin']['avg']:
#        print(b, stat['daylybin']['avg'][b])

def spot_price_summary(spotprice):
    sums = {'avg': 0, 'min': 10000, 'max':0 }
    sum = 0
    for s in spotprice:
        sum += s['cost']
        sums['max'] = max(sums['max'], s['cost'])
        sums['min'] = min(sums['min'], s['cost'])
    sums['avg'] = sum / len(spotprice)
    return sums
    

SAJ_PATHS = "../../logel/logel/html/logel/"
#SAJfields = ['DateTime', 'Month_Totalload_energy[kWh]','Month_InvGenEnergy[kWh]', 'Month_pvenergy[kWh]', 'Month_batdischargeenergy[kWh]', 'Month_batenergy[kWh]']
SAJfields = ['DateTime', 'Year_Totalload_energy[kWh]','Year_InvGenEnergy[kWh]', 'Year_pvenergy[kWh]', 'Year_batdischargeenergy[kWh]', 'Year_batenergy[kWh]']
#'Month_gridconsumed_energy[kWh]' , 'Month_pvconsumed_energy[kWh]'
def get_sajdata(datestr):
    shortdatestr = datestr.replace('-', '')
    fname = SAJ_PATHS + shortdatestr + '_saj.csv'
    sajsummary = {}
    sajdata = ''
    try:
        with open(fname, "r") as fp:
            sajdata = fp.read()
    except:
        sajdata = ''            
    sajdata = sajdata.split("\n")
    headers = sajdata[0].split(';')
    SAJfields = sajdata[0].split(';') #Uncomment to explore more fields
    #print(sajdata[0])
    #print(sajdata[1])
    insync = False
    insynccnt = 0
    for l in sajdata:
        rec = {}
        if l[0:8] == 'DateTime':
            #print('Resync: ', l)
            headers = l.split(';')
            fieldidx = {}
            for v in SAJfields:
                try:
                    fieldidx[v] = headers.index(v)
                except:
                    #print(v, "not found!")
                    fieldidx[v] = -1
            if len(headers) > 4:
                insync = True
                insynccnt = 0
            else:
                insync = False
        elif insync:
            values = l.split(';')
            if len(values) == len(headers):
                insynccnt += 1
                t1 = values[0][0:13] # yyyy-mm-dd HH = 13 chars
                for v in SAJfields:
                    idx = fieldidx[v]
                    if idx != -1:
                        #print(v, idx, values[idx])                    
                        rec[v] = values[idx]
#                    else:
#                        print(v, idx, 'Missing')
                if insynccnt == 1:
                    t0 = values[0][0:13] # yyyy-mm-dd HH = 13 chars
                    rec0 = rec

                if True:                    
                    rec1 = rec
                    rec = {}
                    for f in rec1:
                        if True or 'kWh' in f:
                            try:
                                rec[f] = round(float(rec1[f]) - float(rec0[f]),3) if '[kWh]' in f else rec0[f]
                            except:
                                rec[f] = -1
                    sajsummary[t0] = rec
                if t1 != t0:
                    rec0 = rec1
                    t0 = t1
            else:
                insync = False

    return sajsummary


meterfields = ['DateTime', 'Etot[kWh]','Eouttot[kWh]']

def get_meterdata(datestr):
    shortdatestr = datestr.replace('-', '')
    fname = SAJ_PATHS + shortdatestr + '.csv'
    metersummary = {}
    meterdata = ''
    try:
        with open(fname, "r") as fp:
            meterdata = fp.read()
    except:
        meterdata = ''
    meterdata = meterdata.split("\n")
    headers = meterdata[0].split(';')
    #meterfields = meterdata[0].split(';') #Uncomment to explore more fields
    insync = False
    insynccnt = 0
    for l in meterdata:
        rec = {}
        if l[0:8] == 'DateTime':
            #print('Resync: ', l)
            headers = l.split(';')
            fieldidx = {}
            for v in meterfields:
                try:
                    fieldidx[v] = headers.index(v)
                except:
                    #print(v, "not found!")
                    fieldidx[v] = -1
            if len(headers) > 4:
                insync = True
                insynccnt = 0
            else:
                insync = False
        elif insync:
            values = l.split(';')
            if len(values) == len(headers):
                insynccnt += 1
                t1 = values[0][0:13] # yyyy-mm-dd HH = 13 chars
                for v in meterfields:
                    idx = fieldidx[v]
                    if idx != -1:
                        #print(v, idx, values[idx])                    
                        rec[v] = values[idx]
#                    else:
#                        print(v, idx, 'Missing')
                if insynccnt == 1:
                    t0 = values[0][0:13] # yyyy-mm-dd HH = 13 chars
                    rec0 = rec

                if True:
                    rec1 = rec
                    rec = {}
                    for f in rec1:
                        if True or 'kWh' in f:
                            try:
                                rec[f] = round(float(rec1[f]) - float(rec0[f]),3) if '[kWh]' in f else rec0[f]
                            except:
                                rec[f] = -1
                    metersummary[t0] = rec
                if t1 != t0:
                    rec0 = rec1
                    t0 = t1
            else:
                insync = False

    return metersummary



def calc_gain(spotprice):
    prevday = ''
    sajsummary = {}
    metersummary = {}
    print("Process spot, meter and inverter data")
    for l in spotprice:
        #print(l)
        dt = l['dt']
        day = dt[0:10]

        if day != prevday:
            print(day, end = "        \b\b\b\b\b\b\b\b")
            sajdata = get_sajdata(day)
            prevday = day
            print("s", end = "")
            sajsummary.update(sajdata)
            #for s in sajdata:
            #    sajsummary[s] = sajdata[s]
            meterdata = get_meterdata(day)
            print("m", end = "")
            metersummary.update(meterdata)
            print("", end = "\r")
            #for s in meterdata:
            #    metersummary[s] = meterdata[s]
        else:
            print(".", end = "")
  
    # Now summarize
    print("Summarize hours")
    cost = []
    cost_day = []
    costsum = {}
    prevday = ''
    costsumcnt = 0
    for spot in spotprice:
        dt = spot['dt']
        day = dt[0:10]
        day_hh = dt[0:13].replace('T',' ')
        if prevday != day:
            prevday = day
            if 'dt' in costsum:
                costsum['cost[kr]'] = round(costsum['Etot[kr]'] - costsum['Eout[kr]'],2)
                for f in costsum:
                    if '[' in f:
                        costsum[f] = round(costsum[f], 2)
                    elif f != 'dt':
                        costsum[f] = round(costsum[f]/costsumcnt, 2)

                cost_day.append(costsum)
            costsum = {'dt': day}
            costsumcnt = 0

        rec = {}
        if day_hh in sajsummary:
            rec = { 'dt':day_hh,
                    #'spot': spot['spot'],
                    #'cost': spot['cost'],
                    #'load[kWh]': sajsummary[day_hh]['Month_Totalload_energy[kWh]'],
                    #'load[kr]': round((sajsummary[day_hh]['Month_Totalload_energy[kWh]']*spot['cost'])/100,1),
                    #'PV[kWh]': sajsummary[day_hh]['Month_pvenergy[kWh]'],
                    #'Gen[kWh]': sajsummary[day_hh]['Month_InvGenEnergy[kWh]'],
                    #'Bat[kWh]': sajsummary[day_hh]['Month_batdischargeenergy[kWh]'],
                    'load[kWh]': sajsummary[day_hh]['Year_Totalload_energy[kWh]'],
                    'load[kr]': round((sajsummary[day_hh]['Year_Totalload_energy[kWh]']*spot['cost'])/100,1),
                    'PV[kWh]': sajsummary[day_hh]['Year_pvenergy[kWh]'],
                    'Gen[kWh]': sajsummary[day_hh]['Year_InvGenEnergy[kWh]'],
                    'Bat[kWh]': sajsummary[day_hh]['Year_batdischargeenergy[kWh]'],


                    #'sell[kWh]': round(sajsummary[day_hh]['Month_InvGenEnergy[kWh]']-sajsummary[day_hh]['Month_Totalload_energy[kWh]'],2)
                  }

            bat_consume = rec['load[kWh]'] - rec['PV[kWh]']
            if bat_consume < 0:
                bat_consume = 0
            if bat_consume > rec['Bat[kWh]']:
                bat_consume = rec['Bat[kWh]']
            bat_sell = rec['Bat[kWh]'] - bat_consume
            rec['Bat[kr]'] = round((bat_consume*spot['cost'])/100 + (bat_sell*spot['sell'])/100,1)
            rec['BatU[kr]'] = round((bat_consume*spot['cost'])/100,1)
            rec['BatS[kr]'] = round((bat_sell*spot['sell'])/100,1)

            if day_hh in metersummary:
                rec['Etot[kWh]'] = round(metersummary[day_hh]['Etot[kWh]'],3)
                rec['Etot[kr]'] = round((metersummary[day_hh]['Etot[kWh]']*spot['cost'])/100,1)
                rec['Eout[kWh]'] = round(metersummary[day_hh]['Eouttot[kWh]'],3)
                rec['Eout[kr]'] = round((metersummary[day_hh]['Eouttot[kWh]']*spot['sell'])/100,1)
            else:
                rec['Etot[kWh]'] = 0
                rec['Etot[kr]'] = 0
                rec['Eout[kWh]'] = 0
                rec['Eout[kr]'] = 0
            rec['gain[kr]'] = round(rec['load[kr]'] - rec['Etot[kr]'] + rec['Eout[kr]'],2) 
            rec['cost[kr]'] = round(rec['Etot[kr]'] - rec['Eout[kr]'],2)
            # Sum of input and output should be closed to 0
            rec['diff[kWh]'] = round(rec['Etot[kWh]'] + 0.9*rec['PV[kWh]'] - rec['load[kWh]'] - rec['Eout[kWh]'],3) 

            cost.append(rec)
 
            for f in rec:
                if f != 'dt':
                    if f in costsum:
                        costsum[f] += rec[f]
                    else:
                        costsum[f] = rec[f]
            costsumcnt += 1


    # Add last day entry
    #costsum['cost[kr]'] = round(costsum['Etot[kr]'] - costsum['Eout[kr]'],2)
    for f in costsum:
        if '[' in f:
            costsum[f] = round(costsum[f], 2)
        elif f != 'dt':
            costsum[f] = round(costsum[f]/costsumcnt, 2)

    cost_day.append(costsum)

    first = True
    for rec in cost:
        #print(c)
        if first:
            fieldnbr = 0
            for f in rec:
                if fieldnbr == 0:
                    print("%13s;" % (f), end = "")
                else:
                    print("%9s;" % (f), end = "")
                fieldnbr += 1
            print("")
            first = False
        fieldnbr = 0
        for f in rec:
            if fieldnbr == 0:
                print("%13s;" % (str(rec[f]) ), end = "")
            else:
                print("%9s;" % (str(rec[f]) ), end = "")
            fieldnbr += 1
        print("")


    print("Daily summary")
    ack_cost = 0.0
    ack_value = 0.0

    first = True
    for rec in cost_day:
        ack_cost += rec['cost[kr]']
        ack_value += rec['load[kr]']
        #print(rec, round(ack_value - ack_cost, 2))
        #rec['gain[kr]'] = round(ack_value - ack_cost, 2)

        if first:
            fieldnbr = 0
            for f in rec:
                if fieldnbr == 0:
                    print("%10s;" % (f), end = "")
                else:
                    print("%9s;" % (f), end = "")
                fieldnbr += 1
            print("")
            first = False
        fieldnbr = 0
        for f in rec:
            if fieldnbr == 0:
                print("%10s;" % (str(rec[f]) ), end = "")
            else:
                print("%9s;" % (str(rec[f]) ), end = "")
            fieldnbr += 1
        print("")



    print("Monthly summary")
    prevmonth = ''
    costsumcnt = 0
    costsum = {}
    cost_month = []
    for rec in cost_day:
        dt = rec['dt']
        month = dt[0:7]
        if prevmonth != month:
            prevmonth = month
            if 'dt' in costsum:            
                for f in costsum:
                    if '[' in f:
                        costsum[f] = round(costsum[f], 2)
                    elif f != 'dt':
                        costsum[f] = round(costsum[f]/costsumcnt, 2)
                cost_month.append(costsum)
            costsum = {'dt': month}
            costsumcnt = 0

        for f in rec:
            if f != 'dt':
                if f in costsum:
                    costsum[f] += rec[f]
                else:
                    costsum[f] = rec[f]
        costsumcnt += 1

    # Add last month entry
    for f in costsum:
        if '[' in f:
            costsum[f] = round(costsum[f], 2)
        elif f != 'dt':
            costsum[f] = round(costsum[f]/costsumcnt, 2)
    cost_month.append(costsum)

    first = True
    for rec in cost_month:
        if first:
            for f in rec:
                print("%9s;" % (f), end = "")
            print("")
            first = False
        for f in rec:
            print("%9s;" % (str(rec[f]) ), end = "")
        print("")

        #print(rec)


###########################################################################################

plot_price = False

dt = datetime.datetime.now()
today = dt.strftime("%Y-%m-%d")


parser = argparse.ArgumentParser()
parser.add_argument('--carsoc', help="Start SOC of car (default " + str(car_SOC)+")",
                    type=int, default=car_SOC, required=False)
parser.add_argument('--carsoc2', help="Target SOC of car (default " + str(car_target_SOC)+")",
                    type=int, default=car_target_SOC, required=False)

parser.add_argument('--car', help="Send starttime to car",
                    action='store_true')
parser.add_argument('--saj', help="Send schedule to saj",
                    action='store_true')
parser.add_argument('--calc', help="Calculat cost",
                    action='store_true')                    
parser.add_argument('--price', help="Get price e.g. 2024-05-01:2024-05-31",
                    type=str, default='', required=False)
parser.add_argument('--area', help="Elområde",
                    type=str, default=area, required=False)
parser.add_argument('--plotprice', help="Plot future price",
                    action='store_true')


args = parser.parse_args()
car_SOC = args.carsoc
car_target_SOC = args.carsoc2
area = args.area
plot_price = args.plotprice

if args.price != '':
    [startdate, enddate] = args.price.split(':')
    spotprice = getspot(startdate=startdate, enddate=enddate, area=area)
    if args.calc:
      calc_gain(spotprice)
    else:
      stat = spot_statistics(spotprice)
    exit()


spotprice = getspot(0)
#print(spotprice)
spotprice1 = getspot(1)
#print(spotprice1)
if len(spotprice) == 0:
    spotprice = getspot2(0)
    #print(spotpriceb)
if len(spotprice1) == 0:
    spotprice1 = getspot2(1)
    #print(spotpriceb1)

spotprice.extend(spotprice1)

dt = datetime.datetime.now()
now_hour = dt.strftime("%Y-%m-%dT%H")

allspotprice = spotprice.copy()
#print(spotprice)

while len(spotprice) > 0 and spotprice[0]['dt'][0:13] < now_hour:
    spotprice.pop(0)

sums = {}
i = 0
for s in spotprice:
    date = s['dt'][0:10]
    #spotprice[i]['cost'] = spot2cost(s['spot'])
    if not date in sums:
        sums[date] = {'date': date, 'costavg': 0, 'avg': 0, 'max': -10000, 'min': 10000, 'vsum': 0, 'costsum': 0, 'vcnt': 0}
    sums[date]['vsum'] += s['spot']
    sums[date]['costsum'] += spotprice[i]['cost']
    sums[date]['vcnt'] += 1
    sums[date]['max'] = max(sums[date]['max'], s['spot'])
    sums[date]['min'] = min(sums[date]['min'], s['spot'])
    i += 1
    #if plot_price:
    #    print(s)

days = sorted(list(sums.keys()))
sumd = days[0] + '-' + days[-1]
totalsums = {'date': sumd, 'costavg': 0, 'avg': 0, 'max': -10000, 'min': 10000, 'vsum': 0, 'costsum': 0, 'vcnt': 0}
for d in sums:
    sums[d]['avg'] = round(sums[d]['vsum'] / sums[d]['vcnt'],2)
    sums[d]['costavg'] = round(sums[d]['costsum'] / sums[d]['vcnt'],2)
    totalsums['vsum'] += sums[d]['vsum']
    totalsums['costsum'] += sums[d]['costsum']
    totalsums['vcnt'] += sums[d]['vcnt']
    totalsums['max'] = max(sums[d]['max'], totalsums['max'])
    totalsums['min'] = min(sums[d]['min'], totalsums['min'])

totalsums['avg'] = round(totalsums['vsum'] / totalsums['vcnt'], 2)
totalsums['costavg'] = round(totalsums['costsum'] / totalsums['vcnt'],2)

print("Summary:", days)
for d in sums:
    print(sums[d])
print(totalsums)
i = 0
prevval = spotprice[0]['cost']
for s in spotprice:
    date = s['dt'][0:10]
    nextval = spotprice[i]['cost'] 
    if len(spotprice) > i+1:
        nextval = spotprice[i+1]['cost']
    spotprice[i]['rangeavg'] = {}
    for r in range(0, 8):
        fsum = spotprice[i]['cost']
        j = 1
        while j < r and len(spotprice) > i+j:
            fsum += spotprice[i+j]['cost']
            j += 1
        spotprice[i]['rangeavg'][j] = round(fsum / j, 2)
    
    spotprice[i]['vdiffday'] = round(s['cost'] - sums[date]['costavg'],2)
    spotprice[i]['vdifftot'] = round(s['cost'] - totalsums['costavg'],2)
    if spotprice[i]['vdifftot'] > 0 and prevval < s['cost'] and s['cost'] > nextval:
        spotprice[i]['peak'] = 1
    if spotprice[i]['vdifftot'] < 0 and prevval > s['cost'] and s['cost'] < nextval:
        spotprice[i]['dipp'] = 1
    prevval = s['cost']
    i += 1

if plot_price:
    for s in spotprice:
        print(s)

# Car charge time algorith:
# Between 18:00 and 06:00
# Find lowest cost stretch of time with various lengths
# Depending on SOC and desired SOC
car_energy_kWh = car_total_kWh * (car_target_SOC - car_SOC) / 100

car_charge_time_h_by_current = {}
for car_charge_current in car_charge_current_candidates:
    car_charge_power_kW = car_charge_current*3*230/1000
    car_charge_time_h_by_current[car_charge_current] = round(car_energy_kWh / car_charge_power_kW, 2)

car_charge_time_h = car_charge_time_h_by_current[car_current]

print("car: from %i to %i %%: %0.1f kWh at %i to %i A (%.1f kW) takes %.2f to %.2f hours" %
      (car_SOC, car_target_SOC, car_energy_kWh,
       car_charge_current_candidates[0], car_charge_current_candidates[-1],
       car_charge_power_kW,
       car_charge_time_h_by_current[car_charge_current_candidates[0]], car_charge_time_h_by_current[car_charge_current_candidates[-1]]) )


bat_energy_kWh = bat_total_kWh * (bat_target_SOC - bat_SOC) / 100

bat_charge_time_h_by_power = {}
for bat_charge_power in bat_charge_power_candidates:
    bat_charge_power_kW = bat_charge_power / 1000
    bat_charge_time_h_by_power[bat_charge_power] = round(bat_energy_kWh / bat_charge_power_kW, 2)

bat_charge_time_h = bat_charge_time_h_by_power[bat_power]

print("bat: from %i to %i %%: %0.1f kWh at %i to %i W (%.1f kW) takes %.2f to %.2f hours" %
      (bat_SOC, bat_target_SOC, bat_energy_kWh,
       bat_charge_power_candidates[0], bat_charge_power_candidates[-1],
       bat_charge_power_kW,
       bat_charge_time_h_by_power[bat_charge_power_candidates[0]], bat_charge_time_h_by_power[bat_charge_power_candidates[-1]]),  bat_charge_time_h_by_power)



carspotprice = spotprice
#print('carspotprice 1:')
#for s in carspotprice:
#    print(s)
while len(carspotprice) > 12 and carspotprice[len(carspotprice)-1]['dt'][11:16] > '07:00':
    carspotprice.pop()
#print('## car prices: from', carspotprice[0]['dt'], 'to',carspotprice[-1]['dt'])
#for s in carspotprice:
#    print(s)

candidates = car_charge_time_candidates(carspotprice)
print("## car charge candidates")
for c in candidates:
    print(c, candidates[c])

if car_current >= 14:
    chargehours = math.floor(car_charge_time_h + 1) # Round up to be safe
else:
    chargehours = math.floor(car_charge_time_h+0.3) # Round down, since we usually get more current 
if not chargehours in candidates:
    chargehours = sorted(list(candidates.keys())).pop()
print("Hours: ", car_charge_time_h, '~=', chargehours,'h, at ',car_current, 'A', candidates[chargehours], candidates[chargehours]['dt'][11:16])

print("## SAJ battery charge candidates")
bat_chargehours = round(bat_charge_time_h + 0.4) # Round up to be safe
print("Hours: ", bat_charge_time_h, '~=', bat_chargehours,'h, at ',bat_power, 'W', candidates[bat_chargehours], candidates[bat_chargehours]['dt'][11:16])

saj = {}

summary = spot_price_summary(spotprice)
sajspotprice = allspotprice
print(today,'vs', sajspotprice[0]['dt'][0:10], len(sajspotprice))
while len(sajspotprice) > 12 and sajspotprice[0]['dt'][0:10] == today:
    sajspotprice.pop(0)
print(today,'vs', sajspotprice[0]['dt'][0:10], len(sajspotprice))    

summary2 = spot_price_summary(sajspotprice)

print(summary)
print(summary2)
for s in sajspotprice:
    print(s)
saj['startcharge'] = candidates[bat_chargehours]['dt'][11:16]
saj['futureavg'] = summary['avg']
saj['min'] = summary['min']
saj['max'] = summary['max']
sajh = {}
saj['startchargeh'] = int(saj['startcharge'][0:2])
candidates = car_charge_time_candidates(spotprice)

# Only charge if cost below average-dc
# Only discharge if cost above average+dd
#
#                     ----               --
#                   -     -             -   -
#                -          -         -       - 
#               -               - dipp            -
# -------------3----4----------------------------------
#C0 C1      C2 D0 D1 D2  D3  D4  C3?  D5        C4    C5?
# --       -
#   -------
s = 0
h = 0
if saj['startchargeh'] == 0:
    sajh[s] = {'h': h, 'c': bat_power, 'd': 1, 'cost': sajspotprice[h]['cost'], 'cost2': sajspotprice[h+1-1]['cost'], 's': sajspotprice[h]}
    h += 1
    s += 1
    sajh[s] = {'h': h, 'c': bat_power, 'd': bat_chargehours-1, 'cost': sajspotprice[h]['cost'], 'cost2': sajspotprice[h+bat_chargehours-1-1]['cost'],'s': sajspotprice[h]}
    h += bat_chargehours-1
    s += 1
else:    
    sajh[s] = {'h': h, 'c': 0, 'd': saj['startchargeh'], 'cost': sajspotprice[h]['cost'], 'cost2': sajspotprice[h+saj['startchargeh']-1]['cost'],'s': sajspotprice[h]}
    h += saj['startchargeh']
    s += 1
    sajh[s] = {'h': h, 'c': bat_power, 'd': bat_chargehours, 'cost': sajspotprice[h]['cost'], 'cost2': sajspotprice[h+bat_chargehours-1]['cost'], 's': sajspotprice[h]}
    h += bat_chargehours
    s += 1
h0 = h
belowavgtime = 0    
while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] < summary['avg']:
    belowavgtime += 1    
    h += 1

# Slow charge until cost reaches avg
sajh[s] = {'h': h0, 'c': 1000, 'd': belowavgtime, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+belowavgtime-1]['cost'], 's': sajspotprice[h0]}
#h = belowavgtime
s += 1

# Slow discharge until price is high enough
highenoughtime = 0
h0 = h
while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] < summary['avg']*1.05:
    highenoughtime += 1    
    h += 1

sajh[s] = {'h': h0, 'c': -100, 'd': highenoughtime, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+highenoughtime-1]['cost'], 's': sajspotprice[h0]}
#h = highenoughtime
s += 1

hightime = 0
h0 = h
while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] > summary['avg']*1.05:
    hightime += 1    
    h += 1

sajh[s] = {'h': h0, 'c': -10000, 'd': hightime, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+hightime-1]['cost'], 's': sajspotprice[h0]}
#h += hightime
s += 1

# Slow discharge until price is high enough
highenoughtime = 0
h0 = h
while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] > summary['avg'] and sajspotprice[h]['cost'] < summary['avg']*1.05:
    highenoughtime += 1    
    h += 1
sajh[s] = {'h': h0, 'c': -100, 'd': highenoughtime, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+highenoughtime-1]['cost'], 's': sajspotprice[h0]}
s += 1
# Going up or down?
if sajspotprice[h]['cost'] > summary['avg']: # going up
    duration = 0
    h0 = h
    while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] > summary['avg']*1.05:
        duration += 1
        h += 1
    sajh[s] = {'h': h0, 'c': -3000, 'd': duration, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+duration-1]['cost'], 's': sajspotprice[h0]}
    s += 1
else:
    # Going down
    lowenoughtime = 0
    h0 = h
    while h+1 < len(sajspotprice) and sajspotprice[h]['cost'] < summary['avg']*0.95:
        lowenoughtime += 1
        h += 1
    sajh[s] = {'h': h0, 'c': 0, 'd': lowenoughtime, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+lowenoughtime-1]['cost'], 's': sajspotprice[h0]}
    s += 1

charge = +1
if sajspotprice[h0]['cost'] > summary['avg']:
    charge = -1

duration = 0
h0 = h
while (h+1 < len(sajspotprice)) and (sajspotprice[h]['cost'] < summary['avg']*1.05) and (sajspotprice[h]['cost'] > summary['avg']*0.95):
    duration += 1
    h += 1
sajh[s] = {'h': h0, 'c': charge, 'd': duration, 'cost': sajspotprice[h0]['cost'], 'cost2': sajspotprice[h0+duration-1]['cost'], 's': sajspotprice[h0]}
s += 1



print(saj)
cmds = []
cnum = 0
dnum = 0
for h in sajh:
    print(h, sajh[h])
    if sajh[h]['c'] < 0:
        # Discharge
        cmds.append('D%ibegin=0x%02x00' % (dnum, sajh[h]['h']))
        cmds.append('D%iend=0x%02x00' % (dnum, sajh[h]['h']+sajh[h]['d']))
        cmds.append('D%idays_and_power=0x7F%02x' % (dnum, int(-sajh[h]['c']/100)))
        dnum += 1
    else:
        cmds.append('C%ibegin=0x%02x00' % (cnum, sajh[h]['h']))
        cmds.append('C%iend=0x%02x00' % (cnum, sajh[h]['h']+sajh[h]['d']))        
        cmds.append('C%idays_and_power=0x7F%02x' % (cnum, int(sajh[h]['c']/100)))
        cnum += 1

cmdstr = ','.join(cmds)
print(cmdstr)
for c in cmds:
    print(c)

if args.saj:
  send_saj_commands(cmdstr)

#print(candidates)
for c in candidates:
    print(c, candidates[c])


if args.car:
  set_charge_time(candidates[chargehours]['dt'][11:16])


#numdiff = 0
#diffsum = 0
#i=0
#for s in spotprice:
#    sb = spotpriceb[i]
#    if s['dt'] != sb['dt']:
#        numdiff += 1
#        print("Diff:", i, s, sb)
#    diffsum += s['spot'] - sb['spot']
#    i += 1
#print("Num diffs", numdiff, diffsum)
