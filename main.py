import json
import time
import argparse
import os
import logging
import random

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


from utils import reserve, get_user_credentials

get_current_time = lambda action: (
    time.strftime("%H:%M:%S", time.localtime(time.time() + 8 * 3600))
    if action
    else time.strftime("%H:%M:%S", time.localtime(time.time()))
)
get_current_dayofweek = lambda action: (
    time.strftime("%A", time.localtime(time.time() + 8 * 3600))
    if action
    else time.strftime("%A", time.localtime(time.time()))
)


STARTTIME = "08:00:00"  # 学校开放预约的时间
SLEEPTIME = 3.0  # 每次尝试的间隔，避免高频请求
ENDTIME = "08:01:00"  # 根据学校的预约座位时间+1min即可

ENABLE_SLIDER = False  # 当前学校服务器 securityVerify=0，无需验证码
MAX_ATTEMPT = 1  # 每轮只请求一次，由外层循环按 SLEEPTIME 重试
RESERVE_NEXT_DAY = True  # 预约明天而不是今天的


def unpack_user(user):
    """Read named config fields so adding a school identifier is order-safe."""
    return (
        user.get("username", ""),
        user.get("password", ""),
        user.get("time", []),
        user.get("deptidenc", ""),
        str(user.get("roomid", "")),
        user.get("seatid", []),
        user.get("daysofweek", []),
    )


def login_and_reserve(users, usernames, passwords, action, success_list=None):
    logging.info(
        f"Global settings: \nSTARTTIME: {STARTTIME}\nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )

    if success_list is None:
        success_list = [False] * len(users)

    if not users:
        return success_list

    current_dayofweek = get_current_dayofweek(action)

    # 优化：同一账号多个预约时间段，只登录一次，复用 session
    if action:
        username_list = usernames.split(",")
        password_list = passwords.split(",")
        if len(username_list) != 1 or len(password_list) != 1:
            raise Exception("optimized mode requires one account")
        username = username_list[0]
        password = password_list[0]
    else:
        username, password, _, _, _, _, _ = unpack_user(users[0])

    s = reserve(
        sleep_time=SLEEPTIME,
        max_attempt=MAX_ATTEMPT,
        enable_slider=ENABLE_SLIDER,
        reserve_next_day=RESERVE_NEXT_DAY,
    )

    s.get_login_status()
    login_ok, _ = s.login(username, password)

    if not login_ok:
        logging.error("Skipping reservation because login failed")
        return success_list

    s.requests.headers.update({"Host": "office.chaoxing.com"})

    for index, user in enumerate(users):
        if success_list[index]:
            continue

        _, _, times, deptidenc, roomid, seatid, daysofweek = unpack_user(user)

        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue

        logging.info(
            f"----------- configuration {index + 1} -- {times} -- {seatid} try -----------"
        )

        suc = s.submit(times, deptidenc, roomid, seatid, action)


        success_list[index] = suc



        # 多时间段预约之间增加短随机间隔，模拟再次预约操作


        # 避免连续瞬间发送，同时保持抢座速度


        if index < len(users) - 1:


            delay = random.uniform(0.8, 1.8)


            logging.info(f"Waiting {delay:.2f}s before next reservation")


            time.sleep(delay)

    return success_list


def main(users, action=False):
    current_time = get_current_time(action)
    logging.info(f"start time {current_time}, action {'on' if action else 'off'}")
    attempt_times = 0
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
    success_list = None
    current_dayofweek = get_current_dayofweek(action)
    today_reservation_num = sum(
        1 for d in users if current_dayofweek in d.get("daysofweek")
    )
    if current_time >= ENDTIME:
        logging.info("Reservation window has ended; no request was sent")
        return False
    while current_time < STARTTIME:
        time.sleep(1)
        current_time = get_current_time(action)
    while current_time < ENDTIME:
        attempt_times += 1
        # try:
        success_list = login_and_reserve(
            users, usernames, passwords, action, success_list
        )
        # except Exception as e:
        #     print(f"An error occurred: {e}")
        print(
            f"attempt time {attempt_times}, time now {current_time}, success list {success_list}"
        )
        current_time = get_current_time(action)
        if sum(success_list) == today_reservation_num:
            print(f"reserved successfully!")
            return True
        time.sleep(SLEEPTIME)
    logging.error("Reservation window ended without a confirmed successful reservation")
    return False


def debug(users, action=False):
    logging.warning("Debug mode submits a real reservation immediately; use check for read-only validation")
    logging.info(
        f"Global settings: \nSTARTTIME: {STARTTIME}\nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )
    suc = False
    logging.info(f" Debug Mode start! , action {'on' if action else 'off'}")
    if action:
        usernames, passwords = get_user_credentials(action)
    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username, password, times, deptidenc, roomid, seatid, daysofweek = unpack_user(user)
        if type(seatid) == str:
            seatid = [seatid]
        if action:
            username, password = (
                usernames.split(",")[index],
                passwords.split(",")[index],
            )
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue
        logging.info(f"----------- configuration {index + 1} -- {times} -- {seatid} try -----------")
        s = reserve(
            sleep_time=SLEEPTIME,
            max_attempt=MAX_ATTEMPT,
            enable_slider=ENABLE_SLIDER,
            reserve_next_day=RESERVE_NEXT_DAY,
        )
        s.get_login_status()
        login_ok, _ = s.login(username, password)
        if not login_ok:
            logging.error("Debug stopped because login failed")
            continue
        s.requests.headers.update({"Host": "office.chaoxing.com"})
        suc = s.submit(times, deptidenc, roomid, seatid, action)
        if suc:
            return


def check(users, action=False):
    """Verify login and seat-page parameters without submitting a reservation."""
    logging.info("Read-only check mode: the submit endpoint will not be called")
    usernames, passwords = (None, None)
    if action:
        usernames, passwords = get_user_credentials(action)
    all_ok = True
    for index, user in enumerate(users):
        username, password, times, deptidenc, roomid, seatid, daysofweek = unpack_user(user)
        if type(seatid) == str:
            seatid = [seatid]
        if action:
            username, password = (
                usernames.split(",")[index],
                passwords.split(",")[index],
            )
        s = reserve(
            sleep_time=SLEEPTIME,
            max_attempt=MAX_ATTEMPT,
            enable_slider=False,
            reserve_next_day=RESERVE_NEXT_DAY,
        )
        s.get_login_status()
        login_ok, _ = s.login(username, password)
        if not login_ok:
            logging.error("Configuration %s: login failed; no seat request was sent", index + 1)
            all_ok = False
            continue
        s.requests.headers.update({"Host": "office.chaoxing.com"})
        for seat in seatid:
            result = s.verify_target(roomid, seat, deptidenc)
            target_ok = (
                result["logged_in"]
                and result["page_deptidenc"] == str(deptidenc)
                and result["page_roomid"] == str(roomid)
                and result["page_seatid"] == str(seat)
                and result["has_submit_form"]
                and result.get("room_info_success", False)
                and result.get("server_roomid") == str(roomid)
                and result.get("seat_in_room_range", False)
            )
            logging.info(
                "Configuration %s: room=%s seat=%s read-only check=%s details=%s",
                index + 1,
                roomid,
                seat,
                "passed" if target_ok else "failed",
                result,
            )
            all_ok = all_ok and target_ok
    return all_ok


def get_roomid(args1, args2):
    username = input("请输入用户名：")
    password = input("请输入密码：")
    s = reserve(
        sleep_time=SLEEPTIME,
        max_attempt=MAX_ATTEMPT,
        enable_slider=ENABLE_SLIDER,
        reserve_next_day=RESERVE_NEXT_DAY,
    )
    s.get_login_status()
    s.login(username=username, password=password)
    s.requests.headers.update({"Host": "office.chaoxing.com"})
    encode = input("请输入deptldEnc：")
    s.roomid(encode)


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    parser = argparse.ArgumentParser(prog="Chao Xing seat auto reserve")
    parser.add_argument("-u", "--user", default=config_path, help="user config file")
    parser.add_argument(
        "-m",
        "--method",
        default="reserve",
        choices=["reserve", "debug", "check", "room"],
        help="for debug",
    )
    parser.add_argument(
        "-a",
        "--action",
        action="store_true",
        help="use --action to enable in github action",
    )
    args = parser.parse_args()
    func_dict = {"reserve": main, "debug": debug, "check": check, "room": get_roomid}
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    result = func_dict[args.method](usersdata, args.action)
    if args.method == "check" and not result:
        raise SystemExit(1)
