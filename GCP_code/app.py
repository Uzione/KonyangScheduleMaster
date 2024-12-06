from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

# Chrome WebDriver 초기화
def init_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
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

    driver.execute_script("document.getElementById('id').value = arguments[0];", user_id)
    driver.execute_script("document.getElementById('pass').value = arguments[0];", user_password)
    driver.execute_script("""document.querySelector('.btn_mormal_type').click();""")
        
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
                WebDriverWait(driver, 10).until(EC.url_changes(url))

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

        # 유효성 검사 후 리스트에 추가
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

# 오프라인 출석 체크 함수수
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

        # 2. 입력된 강의 탭으로 이동
        script = """
            let elements = document.querySelectorAll('div.top.offline a strong.title');
            for (let element of elements) {
                if (element.textContent.includes(arguments[0])) {
                    return element.parentElement;
                }
            }
        """
        
        lecture_element = driver.execute_script(script, lecture_name)

        if not lecture_element:
            return jsonify({"status": "failure", "message": "해당 강의명을 찾을 수 없습니다."})

        driver.execute_script("arguments[0].click();", lecture_element)
        WebDriverWait(driver, 10).until(EC.url_changes(url))

        # 3. 해당 강의의 오프라인 출석 탭 이동
        script = """
                    let element = document.querySelector('a.btn_menu_link[href="/lms/class/attendManage/doStudentView.dunet"]');
                    if (element) {
                        element.click();
                    }
                """
        driver.execute_script(script)

        # 4. 입력된 날짜의 <tr> 찾기
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'va_m')))
        
        script = f"""
            let rows = document.querySelectorAll('tr.va_m');
            let targetRow = null;
            let attendanceButton = null;
            let isClicked = false;

            // 1. 목표 날짜가 포함된 행 찾기
            for (let row of rows) {{
                let cells = row.querySelectorAll('td');
                for (let cell of cells) {{
                    if (cell.textContent.includes('{attendance_date}')) {{
                        targetRow = row;
                        break;
                    }}
                }}
                if (targetRow) break;
            }}

            // 2. 목표 날짜가 포함된 행에서 출석 버튼 클릭
            if (targetRow) {{
                attendanceButton = targetRow.querySelector('td a[href="javascript:;"]');
                if (attendanceButton) {{
                    try {{
                        attendanceButton.scrollIntoView();
                        attendanceButton.click();
                        let isClicked = true; // 성공적으로 클릭
                    }} catch (e) {{
                        let isClicked = false; // 클릭 실패 시 false 반환
                    }}
                }}
            }}

            // 3. 출석체크 버튼이 없다면 동일 날짜 내 다른 tr에서 버튼 클릭 시도
            if (!isClicked) {{
                for (let row of rows) {{
                    if (row !== targetRow) {{
                        let cells = row.querySelectorAll('td');
                        for (let cell of cells) {{
                            if (cell.textContent.includes('{attendance_date}')) {{
                                attendanceButton = row.querySelector('td a[href="javascript:;"]');
                                if (attendanceButton) {{
                                    try {{
                                        attendanceButton.click();
                                        return true; // 성공적으로 클릭
                                    }} catch (e) {{
                                        return false; // 클릭 실패 시 false 반환
                                    }}
                                }}
                            }}
                        }}
                    }}
                    if (isClicked) break;
                }}
            }}

            return false; // 버튼을 찾지 못함
        """

        result = driver.execute_script(script)

        if result:
            print("[success] 출석 버튼 클릭 완료")
        else:
            return jsonify({"status": "failure", "message": "출석 버튼을 찾을 수 없습니다."})

        # 5. OTP 코드 입력 및 인증
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'otpcode')))
        script = f"""
            // OTP 코드 입력
            let otpInput = document.getElementById('otpcode');
            if (otpInput) {{
                otpInput.value = '{otp_code}';
            }}

            // 인증 버튼 클릭
            let certificationButton = document.querySelector('.btn_certification');
            if (certificationButton) {{
                certificationButton.click();
            }}
        """

        driver.execute_script(script)
        


        # 6. 인증 결과 확인
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
