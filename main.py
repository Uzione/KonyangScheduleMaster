from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

# ChromeDriver 경로 환경 변수로 설정 (Cloud Run에서는 기본 경로 사용 가능)
driver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/lib/chromium-driver')

@app.route('/get_schedule', methods=['POST'])
def get_schedule():
    # 클라이언트에서 받은 데이터
    data = request.get_json()
    user_id = data.get('user_id')
    user_password = data.get('user_password')
    
    # 아이디와 비밀번호 필수 체크
    if not user_id or not user_password:
        return jsonify({"error": "아이디와 비밀번호는 필수입니다."}), 400

    url = "https://lms.konyang.ac.kr/login/doLoginPage.dunet"
    
    # 크롤링 함수 실행
    schedule_data = auto_login_and_crawl(url, user_id, user_password)
    
    if schedule_data:
        return jsonify(schedule_data), 200
    else:
        return jsonify({"error": "강의 정보를 가져올 수 없습니다."}), 500

def auto_login_and_crawl(url, user_id, user_password):
    # ChromeDriver 경로 설정
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)

    try:
        driver.get(url)

        # 로그인 수행
        driver.find_element(By.ID, "id").send_keys(user_id)
        driver.find_element(By.ID, "pass").send_keys(user_password)
        driver.find_element(By.CSS_SELECTOR, ".btn_mormal_type").click()

        # 로그인 후 페이지 로딩 대기
        WebDriverWait(driver, 10).until(EC.url_changes(url))
        print("로그인 성공! 현재 페이지:", driver.current_url)

        # 강의 목록을 찾기 위해 페이지 소스 가져오기
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # 강의명 추출
        lecture_container = soup.find("div", id="landing_lec_box_container")
        lecture_elements = lecture_container.find_all("li", class_="box") if lecture_container else []

        lectures = []
        for lecture_element in lecture_elements:
            lecture_name = lecture_element.find("strong", class_="title").text.strip()
            print(f"\n강의명: {lecture_name}")

            # 강의 정보 추가
            lectures.append({
                '강의명': lecture_name,
                # 추가적인 정보 처리 가능
            })

        return lectures
        
    except Exception as e:
        print("오류 발생:", str(e))
        return None

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

if __name__ == "__main__":
    # Cloud Run에서 서버가 실행될 때는 이 부분을 사용
    app.run(host='0.0.0.0', port=8080)
