import logging
import time
import json
import asyncio
from .util.sm3 import sm3
from urllib.parse import quote
from pyDes import des, CBC, PAD_PKCS5
import base64

_LOGGER = logging.getLogger(__name__)

WXMP_GAS_URL = "https://zt.bjgas.com:6443/wxmpgas/wxmp?data="

WXMP_APP_ID = "wx2a6065eb9e700a28"

REQ_INFO = "nbUserInfoAcctQuery"
REQ_WEK = "nbCMMWEKQryMP"
REQ_DEC = "nbCMMDECQryMP"

USER_TYPE = "04"


class AuthFailed(Exception):
    pass


class InvalidData(Exception):
    pass


class GASData:
    def __init__(self, session, wxsign, user_code):
        self._session = session
        self._wxsign = wxsign
        self._user_code = user_code
        self._info = {}
        self._des = des(b"424A4741", mode=CBC, IV=b'4D505758', pad=None, padmode=PAD_PKCS5)

    def common_headers(self):
        headers = {
            "Host": "zt.bjgas.com:6443",
            "Connection": "keep-alive",
            # "Content-Length": "109",
            # "Tocken": "1be36023b5bd0e332b3f58e34098544539ab7fa7f8a3f6b983ff4400e3496b68",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Wechat-Hostsign": f"{self._wxsign}",
            "Accept-Encoding": "gzip,compress,br,deflate",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.31(0x18001f34) NetType/WIFI Language/zh_CN",
            # "Referer": "https://servicewechat.com/wx2a6065eb9e700a28/30/page-frame.html",
        }

        return headers

    def data_concat(self, req_type):
        return req_type + "|" + self._user_code + "|" + USER_TYPE + "|" + str(
            round(time.time() * 1000)) + "|" + WXMP_APP_ID + "|"

    def des_enc(self, text):
        d = self._des.encrypt(text.encode('utf-8'))
        return base64.b64encode(d).decode('utf-8')

    def des_dec(self, text):
        d = base64.b64decode(text)
        return self._des.decrypt(d).decode('utf-8')

    async def async_get_info(self, user_code):
        headers = self.common_headers()

        original_data = self.data_concat(REQ_INFO)
        _LOGGER.warning("original_data:%s", original_data)
        encrypt_data = self.des_enc(original_data)
        _LOGGER.warning("encrypt_data:%s", encrypt_data)
        tocken = sm3(encrypt_data).lower()
        _LOGGER.warning("tocken:%s", tocken)
        headers["Tocken"] = tocken

        urlencode_data = quote(encrypt_data)
        _LOGGER.warning("urlencode_data:%s", urlencode_data)
        r = await self._session.post(WXMP_GAS_URL + urlencode_data,
                                     headers=headers,
                                     data={"data": urlencode_data},
                                     timeout=10)
        if r.status == 200:
            ret = await r.read()
            _LOGGER.warning("gas ret:%s", ret)
            result = json.loads(ret)
            encrypt_response = result[0]['data']
            decrypt_data = self.des_dec(encrypt_response)
            _LOGGER.warning("gas ret decrypt_data:%s", decrypt_data)
            data_arr = decrypt_data.split('|')
            if data_arr[0] == '0001':
                self._info[user_code]["month_reg_qty"] = float(data_arr[3])
                self._info[user_code]["balance"] = float(data_arr[4])
                self._info[user_code]["current_price"] = float(data_arr[5])
                self._info[user_code]["last_update"] = data_arr[6]
                self._info[user_code]["battery_voltage"] = float(data_arr[8])
                self._info[user_code]["mtr_status"] = data_arr[9]
                if float(data_arr[16]) > 0:
                    self._info[user_code]["current_level"] = 1
                    self._info[user_code]["current_level_remain"] = float(data_arr[16])
                else:
                    self._info[user_code]["current_level"] = 2
                    self._info[user_code]["current_level_remain"] = float(data_arr[18])
                self._info[user_code]["year_consume"] = float(data_arr[19])
            else:
                raise InvalidData(f"async_get_info response decrypt_data = {decrypt_data}")
        else:
            raise InvalidData(f"async_get_info response status_code = {r.status}")

    async def async_get_mon(self, user_code):
        headers = self.common_headers()

        original_data = self.data_concat(REQ_DEC)
        _LOGGER.warning("original_data:%s", original_data)
        encrypt_data = self.des_enc(original_data)
        _LOGGER.warning("encrypt_data:%s", encrypt_data)
        tocken = sm3(encrypt_data).lower()
        _LOGGER.warning("tocken:%s", tocken)
        headers["Tocken"] = tocken

        urlencode_data = quote(encrypt_data)
        _LOGGER.warning("urlencode_data:%s", urlencode_data)
        r = await self._session.post(WXMP_GAS_URL + urlencode_data,
                                     headers=headers,
                                     data={"data": urlencode_data},
                                     timeout=10)
        if r.status == 200:
            ret = await r.read()
            _LOGGER.warning("gas ret:%s", ret)
            result = json.loads(ret)
            encrypt_response = result[0]['data']
            decrypt_data = self.des_dec(encrypt_response)
            _LOGGER.warning("gas ret decrypt_data:%s", decrypt_data)
            data_arr = decrypt_data.split(',')
            if data_arr[0] == '0001':
                mon_bills = []
                for i in range(2, len(data_arr), 1):
                    str_arr = data_arr[i].split('|')
                    if len(str_arr) != 4:
                        continue
                    mon_bills.append({"mon": str_arr[1], "regQty": str_arr[2]})
                self._info[user_code]["monthly_bills"] = mon_bills
            else:
                raise InvalidData(f"async_get_mon response decrypt_data = {decrypt_data}")
        else:
            raise InvalidData(f"async_get_mon response status_code = {r.status}")

    async def async_get_week(self, user_code):
        headers = self.common_headers()

        original_data = self.data_concat(REQ_WEK)
        _LOGGER.warning("original_data:%s", original_data)
        encrypt_data = self.des_enc(original_data)
        _LOGGER.warning("encrypt_data:%s", encrypt_data)
        tocken = sm3(encrypt_data).lower()
        _LOGGER.warning("tocken:%s", tocken)
        headers["Tocken"] = tocken

        urlencode_data = quote(encrypt_data)
        _LOGGER.warning("urlencode_data:%s", urlencode_data)
        r = await self._session.post(WXMP_GAS_URL + urlencode_data,
                                     headers=headers,
                                     data={"data": urlencode_data},
                                     timeout=10)
        if r.status == 200:
            ret = await r.read()
            _LOGGER.warning("gas ret:%s", ret)
            result = json.loads(ret)
            encrypt_response = result[0]['data']
            decrypt_data = self.des_dec(encrypt_response)
            _LOGGER.warning("gas ret decrypt_data:%s", decrypt_data)
            data_arr = decrypt_data.split(',')
            if data_arr[0] == '0001':
                day_bills = []
                for i in range(2, len(data_arr), 1):
                    str_arr = data_arr[i].split('|')
                    if len(str_arr) != 5:
                        # print(str_arr)
                        continue
                    day_bills.append({"day": str_arr[1], "regQty": str_arr[2]})
                self._info[user_code]["daily_bills"] = day_bills
            else:
                raise InvalidData(f"async_get_week response decrypt_data = {decrypt_data}")
        else:
            raise InvalidData(f"async_get_week response status_code = {r.status}")

    async def async_get_data(self):
        self._info = {self._user_code: {}}
        tasks = [
            self.async_get_info(self._user_code),
            self.async_get_mon(self._user_code),
            self.async_get_week(self._user_code),
        ]
        await asyncio.wait(tasks)
        _LOGGER.debug(f"Data {self._info}")
        return self._info
