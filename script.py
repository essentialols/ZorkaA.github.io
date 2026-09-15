import requests
from bs4 import BeautifulSoup
s=requests.Session()
base='https://www.worldvaluessurvey.org/'
page=s.get(base+'AJDocumentationSmpl.jsp?CndWAVE=6',timeout=60)
print('page',page.status_code,page.url,len(page.content))
data={'ulthost':'WVS','CMSID':'','CndWAVE':'6','SAID':'0','DOID':'11887','AJArchive':'WVS Data Archive','EdFunction':'','DOP':'','XU':'','PUB':''}
r=s.post(base+'AJDownloadLicense.jsp',data=data,timeout=60,allow_redirects=True)
print('license',r.status_code,r.url,len(r.content),r.headers.get('content-type'),r.headers.get('content-disposition'))
print(r.text[:12000])
print('--- links/forms ---')
soup=BeautifulSoup(r.text,'html.parser')
for f in soup.find_all('form'):
    print('FORM',f.get('action'),f.get('method'),[(i.get('name'),i.get('value'),i.get('type')) for i in f.find_all('input')])
for a in soup.find_all('a',href=True):
    print('A',a.get_text(' ',strip=True)[:120],a['href'])
