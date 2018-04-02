from __future__ import print_function # Python 2/3 compatibility
from urllib.request import Request, urlopen
import re
from bs4 import BeautifulSoup
import sqlite3
import time
import sys
import urllib.request
import xmltodict
import json
import decimal
import boto3
from xml.etree.ElementTree import parse

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

from datetime import date, datetime
url = 'http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev?'
key = '49rKGilAY%2FInAVDmv5kRUue6TsvmfpJ6t4zvl8Nzflwlmgm9rwMTsOt5NLfs7cT0z83PJbISAFCsI7jnO5HXYg%3D%3D'

numOfRows = '1000'
url+= 'ServiceKey='+key + '&numOfRows='+ numOfRows
#url+='ServiceKey='+key + '&LAWD_CD='+loc_param+'&DEAL_YMD='+date_param
# 출력 파일 명
OUTPUT_FILE_NAME = 'output.json'

conn = sqlite3.connect('loc.db')
c = conn.cursor()
c.execute('SELECT * FROM location')
locData = c.fetchall()
conn.commit()


#print url+queryParams

todayM = date.today().strftime('%Y%m')

dynamodb = boto3.resource('dynamodb')

table_name = 'aptTrx3'

dynamodb_client = boto3.client('dynamodb')

existing_tables  = dynamodb_client.list_tables()['TableNames']

if table_name not in existing_tables:
    table = dynamodb.create_table(
        TableName='aptTrx3',
        KeySchema=[
            {
                'AttributeName': 'trxYear',
                'KeyType': 'HASH'  #Partition key
            },
            {
                'AttributeName': 'keyCodeB',
                'KeyType': 'RANGE'  #Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'trxYear',
                'AttributeType': 'N'
            },
            {
                'AttributeName': 'keyCodeB',
                'AttributeType': 'S'
            },

        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 30,
            'WriteCapacityUnits': 30
        }
    )
    print('creating table~ wait a moment')
    table.meta.client.get_waiter('table_exists').wait(TableName='aptTrx3')
    print('create table complete!')

#지정된 지역코드 및 월의 아파트 거래 데이터를 받아와서 db에 insert
def howmuch(loc_param, date_param):
	numb = 0
	res_list = []
	res=''
	printed = False
	#print(loc_param, date_param)
	request = Request(url+'&LAWD_CD='+loc_param+'&DEAL_YMD='+date_param)
	print(url+'&LAWD_CD='+loc_param+'&DEAL_YMD='+date_param)
	res_body = urlopen(request).read()
	rp_dict = xmltodict.parse(res_body)
	rp_json = json.dumps(rp_dict, ensure_ascii=False, indent=4, cls=DecimalEncoder)
	#print(rp_dict)
	#print(rp_json)
	open_output_file = open(OUTPUT_FILE_NAME, 'w')
	open_output_file.write(rp_json)
	open_output_file.close()

	table = dynamodb.Table('aptTrx3')
	# WHEREunion_bldg_mngm_noLIKE'1111041001350300000400000'
	# 도로명시군구코드+도로명코드+도로명일련번호코드+도로명지상지하코드+도로명건물본번호+부번호 => keyCodeB
	#parsed[7] + parsed[10] + parsed[8] + parsed[9] + parsed[5] + parsed[6]
	#pCode = loc_param + date_param + str(numb)
	numb=0
	with open("output.json") as json_file:
		apttrxs = json.load(json_file, parse_float = decimal.Decimal)
		rep = apttrxs['response']
		bd = rep['body']['items']
		#print(bd['item'])
		keyCodeB = ''
		for item in bd['item']:
			#item = str(item)
			keyCodeB = item['법정동시군구코드'] + item['법정동읍면동코드'] + item['법정동본번코드'] + item['법정동부번코드'] + '|' + item['전용면적'] + '|' + item['층']
				
			trxYear = int(item['년'])
			trxMon = int(item['월'])
			trxPrice = item['거래금액']
			trxPriceN = int(re.sub(',','',trxPrice))
			area = item['전용면적']
			flr = item['층']

			info = item
			print(trxYear,keyCodeB,trxPriceN)
			table.put_item(
				Item={
					'trxYear': trxYear,
					'trxMon': trxMon,
					'keyCodeB': keyCodeB,
					'trxPrice': trxPriceN,
					'area': area,
					'flr': flr,
					'info': info,
				}
			)


cnt = 0
for loc in locData:

    loc_param = loc[1]

    end = False
    startY = 2006
    startM = 1
    endY = 2017
    endM = 10

    while (not end):

        if (startM > 9):
            date_param = str(startY) + str(startM)
        else:
            date_param = str(startY) + '0' + str(startM)

        howmuch(loc_param, date_param)

        if (endY < startY):
            end = True
        elif (endY == startY):
            if (endM <= startM):
                end = True

        if (startM == 12):
            startM = 1
            startY += 1
        else:
            startM += 1