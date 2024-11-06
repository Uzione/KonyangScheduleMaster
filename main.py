from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import os

def auto_login_and_crawl(url, user_id, user_password):
    # ChromeDriver 경로 설정 (Cloud Run 환경에 맞게 설정)
    driver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/lib/chromium-driver')
    service = Service(driver_path)
    
    # ChromeOptions 설정 (Headless 모드 사용)
    options = webdriver.ChromeOptions()
    options.binary_location = os.environ.get('CHROMIUM_BIN', '/usr/bin/chromium')

    # Headless 모드로 Chrome 실행
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # 로그인 페이지 열기
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

        for lecture_element in lecture_elements:
            # 강의명 추출
            lecture_name = lecture_element.find("strong", class_="title").text.strip()
            print(f"\n강의명: {lecture_name}")

            # 강의 링크 가져오기
            lecture_link = lecture_element.find("a", href=True)["href"]

            # 강의 페이지로 이동
            driver.execute_script(lecture_link)

            # 오프라인 출석탭으로 이동
            try:
                # 로딩 시간을 짧게 설정한 후, 요소가 나타나면 즉시 이동
                offline_attendance_tab = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.btn_menu_link[href="/lms/class/attendManage/doStudentView.dunet"]'))
                )
                driver.execute_script("arguments[0].click();", offline_attendance_tab)
                time.sleep(0.5)  # 페이지 로딩 시간 최소화

                # 오프라인 출석 페이지에서 데이터 가져오기
                page_source = driver.page_source
                lectures_data = parse_attendance_data(page_source, lecture_name)

                if lectures_data:
                    for data in lectures_data:
                        print(f"강의 정보: {data}")
                else:
                    print("수업 정보가 없는 강의입니다.")

            except Exception as e:
                print("오프라인 출석탭 이동 중 오류 발생:", str(e))

        input("작업을 확인한 후 Enter 키를 눌러 종료하세요...")

    except Exception as e:
        print("로그인 중 오류 발생:", str(e))
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
    url = "https://lms.konyang.ac.kr/login/doLoginPage.dunet"
    user_id = input("아이디를 입력하세요: ")
    user_password = input("비밀번호를 입력하세요: ")

    auto_login_and_crawl(url, user_id, user_password)
