from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import os
import urllib.parse

app = Flask(__name__)

# Chrome WebDriver 초기화
def init_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 시각적 확인이 필요하면 이 줄을 주석 처리
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--single-process")
    service = Service(executable_path="/usr/local/bin/chromedriver-linux64/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)



# 아이디 인증
@app.route('/verify_id', methods=['POST'])
def verify_id():
    data = request.get_json()
    user_id = data.get('user_id')
    user_password = data.get('user_password')
    
    url = "https://lms.konyang.ac.kr/login/doLoginPage.dunet"
    
    driver = init_webdriver()
    
    try:
        login_to_lms(driver, url, user_id, user_password)
        return jsonify({"status": "success", "message": "인증되었습니다."})

    except Exception as e:
        return jsonify({"status": "failure", "message": str(e)})
    finally:
        driver.quit()
    

# 로그인 함수
def login_to_lms(driver, url, user_id, user_password):
    driver.get(url)

    driver.find_element(By.ID, "id").send_keys(user_id)
    driver.find_element(By.ID, "pass").send_keys(user_password)
    driver.find_element(By.CSS_SELECTOR, ".btn_mormal_type").click()
        
    # URL 변화 대기
    WebDriverWait(driver, 5).until(EC.url_changes(url))

# 강의 정보 불러오기
@app.route('/get_schedule', methods=['POST'])
def get_schedule():
    data = request.get_json()
    user_id = data.get('user_id')
    user_password = data.get('user_password')

    url = "https://lms.konyang.ac.kr/login/doLoginPage.dunet"
    
    schedule_data = auto_login_and_crawl(url, user_id, user_password)
    
    return jsonify(schedule_data)

def auto_login_and_crawl(url, user_id, user_password):
    driver = init_webdriver()

    try:
        driver.get(url)
        
        login_to_lms(driver,url,user_id,user_password)

        # 강의 목록을 찾기 위해 페이지 소스 가져오기
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # 강의명 추출
        lecture_container = soup.find("div", id="landing_lec_box_container")
        lecture_elements = lecture_container.find_all("li", class_="box") if lecture_container else []

        lectures_data = []
        for lecture_element in lecture_elements:
            lecture_name = lecture_element.find("strong", class_="title").text.strip()
            lecture_link = lecture_element.find("a", href=True)["href"]

            # 강의 페이지로 이동
            driver.execute_script(lecture_link)

            try:
                # 오프라인 출석탭으로 이동
                offline_attendance_tab = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.btn_menu_link[href="/lms/class/attendManage/doStudentView.dunet"]'))
                )
                driver.execute_script("arguments[0].click();", offline_attendance_tab)
                time.sleep(0.5)

                # 오프라인 출석 페이지에서 데이터 가져오기
                page_source = driver.page_source
                lecture_info = parse_attendance_data(page_source, lecture_name)
                if lecture_info:
                    lectures_data.extend(lecture_info)

            except Exception as e:
                print("오프라인 출석탭 이동 중 오류 발생:", str(e))

        return {"status": "success", "data": lectures_data}

    except Exception as e:
        return {"status": "failure", "message": str(e)}

    finally:
        driver.quit()

def parse_attendance_data(page_source, lecture_name):
    # BeautifulSoup로 페이지 소스 파싱
    soup = BeautifulSoup(page_source, 'html.parser')
    rows = soup.find_all('tr', class_='va_m')
    lectures = []
    last_week = None  # 이전 주차 정보를 저장

    for row in rows:
        tds = row.find_all('td')

        if len(tds) < 4:
            continue  # 4개 이상의 <td>가 없으면 건너뜀

        # 주차 정보 처리
        week_td = tds[0]
        if week_td.has_attr('rowspan'):
            week = week_td.text.strip()
            last_week = week
            date = tds[1].text.strip().replace('"', '') if len(tds) > 1 else None
            class_number = tds[2].text.strip() if len(tds) > 2 else None
            supplementary_info = tds[3].text.strip() if len(tds) > 3 and tds[3].text.strip() != '' else '-'
        else:
            week = last_week
            date = tds[0].text.strip().replace('"', '') if len(tds) > 0 else None
            class_number = tds[1].text.strip() if len(tds) > 1 else None
            supplementary_info = tds[2].text.strip() if len(tds) > 2 and tds[2].text.strip() != '' else '-'

        # 유효한 정보를 확인하고 리스트에 추가
        if date and class_number and date != '6' and date.startswith('20'):
            supplementary_info = ' '.join(supplementary_info.split())
            lecture_info = {
                '강의명': lecture_name,
                '주차': week,
                '일자': date,
                '수업 교시': class_number,
                '보강 정보': supplementary_info
            }
            lectures.append(lecture_info)

    return lectures if lectures else None

# 강의 이동 및 출석 처리 API
@app.route('/mark_attendance', methods=['GET'])
def mark_attendance():
    lecture_name = request.args.get("lecture_name")
    user_id = request.args.get('user_id')
    user_password = request.args.get('user_password')
    attendance_date = request.args.get('attendance_date')
    otp_code = request.args.get('otp_code')

    url = "https://lms.konyang.ac.kr/login/doLoginPage.dunet"
    driver = init_webdriver()
    try:
        # 1. 로그인
        login_to_lms(driver, url, user_id, user_password)

        # 2. 강의 이동
        lecture_element = None
        lecture_list = driver.find_elements(By.CSS_SELECTOR, 'div.top.offline a strong.title')
        for element in lecture_list:
            if lecture_name in element.text:
                lecture_element = element.find_element(By.XPATH, "..")
                break

        if not lecture_element:
            return jsonify({"status": "failure", "message": "해당 강의명을 찾을 수 없습니다."})

        lecture_element.click()

        # 3. 오프라인 출석 탭 이동
        offline_attendance_tab = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.btn_menu_link[href="/lms/class/attendManage/doStudentView.dunet"]'))
            )
        driver.execute_script("arguments[0].click();", offline_attendance_tab)
        time.sleep(0.5)

        # 4. 특정 날짜의 <tr> 찾기 (날짜가 포함된 tr 선택)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'va_m')))
        rows = driver.find_elements(By.CSS_SELECTOR, 'tr.va_m')
        target_row = None

        for row in rows:
            date_cells = row.find_elements(By.TAG_NAME, 'td')
            for date_cell in date_cells:
                if attendance_date in date_cell.text:
                    target_row = row
                    break
            if target_row:
                break

        if not target_row:
            return jsonify({"status": "failure", "message": "해당 날짜의 출석 정보를 찾을 수 없습니다."})

        # 5. 해당 날짜의 출석 버튼 클릭 (자바스크립트로 URL 변경)
        attendance_button = None

        try:
            attendance_button = target_row.find_element(By.CSS_SELECTOR, 'td a[href="javascript:;"]')
            driver.execute_script("arguments[0].scrollIntoView();", attendance_button)
            driver.execute_script("arguments[0].click();", attendance_button)
        except Exception as e:
            # 동일한 날짜 내 다른 tr을 찾아 자바스크립트 실행
            for row in rows:
                date_cells = row.find_elements(By.TAG_NAME, 'td')
                for date_cell in date_cells:
                    if attendance_date in date_cell.text:
                        if row != target_row:
                            try:
                                attendance_button = row.find_element(By.CSS_SELECTOR, 'td a[href="javascript:;"]')
                                driver.execute_script("arguments[0].scrollIntoView();", attendance_button)
                                driver.execute_script("arguments[0].click();", attendance_button)
                                break
                            except Exception as inner_e:
                                print(f"[다른 tr 출석 버튼 클릭 실패]: {inner_e}")
                if attendance_button:
                    break

        if not attendance_button:
            return jsonify({"status": "failure", "message": "출석 버튼을 찾을 수 없습니다."})

        # 6. OTP 코드 입력 및 인증
        otp_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'otpcode'))
        )
        otp_input.send_keys(otp_code)

        certification_button = driver.find_element(By.CLASS_NAME, 'btn_certification')
        certification_button.click()

        # 7. 인증 결과 대기 (WebDriverWait 사용)
        try:
            WebDriverWait(driver, 10).until(EC.alert_is_present())  # alert이 나타날 때까지 대기
            alert_message = driver.switch_to.alert.text  # 인증 후 브라우저 alert 메시지 확인
            driver.switch_to.alert.accept()  # alert을 닫기

            # 인증 결과 메시지 처리
            if "인증번호가 일치하지 않습니다." in alert_message:
                return jsonify({"status": "failure", "message": "인증번호가 일치하지 않습니다."})
            elif "출석 인증 완료" in alert_message:
                return jsonify({"status": "success", "message": "출석 인증 완료!"})

        except Exception as e:
            return jsonify({"status": "failure", "message": "인증 과정에서 오류 발생."})

    except Exception as e:
        return jsonify({"status": "failure", "message": str(e)})

    finally:
        driver.quit()

if __name__ == "__main__":
    # Cloud Run에서 서버가 실행될 때는 이 부분을 사용
    app.run(host='0.0.0.0', port=8080)
