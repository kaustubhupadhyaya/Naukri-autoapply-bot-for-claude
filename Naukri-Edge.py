import pandas as pd
import time
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService




firstname='Upadhyaya'                        #Add your LastName
lastname='Kaustubh'                         #Add your FirstName
joblink=[]                          #Initialized list to store links
maxcount=100                         #Max daily apply quota for Naukri
keywords=['Data Engineer', 'Python', 'ETL', 'SQL']                    #Add you list of role you want to apply comma seperated
location = 'Bengaluru, Karnataka, India'                       #Add your location/city name for within India or remote
applied =0                          #Count of jobs applied sucessfully
failed = 0                          #Count of Jobs failed
applied_list={
    'passed':[],
    'failed':[]
}                                   #Saved list of applied and failed job links for manual review
yournaukriemail = 'kaustubh.upadhyaya1@gmail.com'
yournaukripass = '9880380081@kK'
try:

    service = EdgeService(executable_path=r"C:\WebDrivers\msedgedriver.exe")
    driver = webdriver.Edge(service=service)
    driver.get('https://login.naukri.com/')
    uname=driver.find_element(By.ID, 'usernameField')
    uname.send_keys(yournaukriemail)
    passwd=driver.find_element(By.ID, 'passwordField')
    passwd.send_keys(yournaukripass)
    passwd.send_keys(Keys.ENTER)

except Exception as e:
    print('Webdriver exception:', e)
    exit()
time.sleep(10)
for k in keywords:
    for i in range(2):
        if location=='':
            url = "https://www.naukri.com/"+k.lower().replace(' ','-')+"-"+str(i+1)
        else: url = "https://www.naukri.com/"+k.lower().replace(' ','-')+"-jobs-in-"+location.lower().replace(' ','-')+"-"+str(i+1)
        driver.get(url)
        print(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source,'html5lib')
        results = soup.find(class_='list')
        if results:
            job_elems = results.find_all('article',class_='jobTuple bgWhite br4 mb-8')
            for job_elem in job_elems:
                joblink.append(job_elem.find('a',class_='title fw500 ellipsis').get('href'))
        else:
            print("No job list found on page:", url)


# Scrape job titles from Naukri and use them as keywords
job_titles = set()
try:
    driver.get("https://www.naukri.com/data-engineer-jobs")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    for elem in soup.find_all("a", class_="title fw500 ellipsis"):
        title = elem.get_text(strip=True)
        if title:
            job_titles.add(title)
except Exception as e:
    print('Error scraping job titles:', e)

keywords = list(job_titles)

# Save scraped keywords to a file for later viewing
with open('scraped_keywords.py', 'w', encoding='utf-8') as f:
    f.write('# This file contains the scraped job keywords from Naukri\n\n')
    f.write('keywords = [\n')
    for kw in keywords:
        f.write(f"    '{kw}',\n")
    f.write(']\n')

for i in joblink:
    time.sleep(3)
    driver.get(i)   
    if applied <=maxcount:
        try:
            time.sleep(3)
            driver.find_element_by_xpath("//*[text()='Apply']").click()
            time.sleep(2)
            applied +=1
            applied_list['passed'].append(i)
            print('Applied for ',i, " Count", applied)

        except Exception as e: 
            failed+=1
            applied_list['failed'].append(i)
            print(e, "Failed " ,failed)
        try:    
            if driver.find_element_by_xpath("//*[text()='Your daily quota has been expired.']"):
                print('MAX Limit reached closing browser')
                driver.close()
                break
            if driver.find_element_by_xpath("//*[text()=' 1. First Name']"):
                driver.find_element_by_xpath("//input[@id='CUSTOM-FIRSTNAME']").send_keys(firstname)
            if driver.find_element_by_xpath("//*[text()=' 2. Last Name']"):
                driver.find_element_by_xpath("//input[@id='CUSTOM-LASTNAME']").send_keys(lastname)
            if driver.find_element_by_xpath("//*[text()='Submit and Apply']"):
                driver.find_element_by_xpath("//*[text()='Submit and Apply']").click()
        except:
            pass
            
    else:
        driver.close()
        break
print('Completed applying closing browser saving in applied jobs csv')
try:
    driver.close()
except:pass
csv_file = "naukriapplied.csv"
final_dict= dict ([(k, pd.Series(v)) for k,v in applied_list.items()])
df = pd.DataFrame.from_dict(final_dict)
df.to_csv(csv_file, index = False)