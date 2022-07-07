# pylint: disable=locally-disabled, multiple-statements, line-too-long, missing-module-docstring, missing-function-docstring, missing-class-docstring, invalid-name, pointless-string-statement, broad-except
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dateutil.parser import parse
import googlemaps

# secrets
from autoflex_secrets import GMAPS_API_KEY, HOME_PLACE_ID, SYFT_EMAIL, SYFT_PASSWORD, login_headers, logout_headers, refresh_headers, syftheaders, syft_worker_url, BLACKLISTED_VENUE_NAMES

# API client
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

class SyftSession():
    def __init__(self):
        self.logged_in          = False
        self.login_failed       = False
        self.access_token       = None
        self.refresh_token      = None

        self.place_cache = {
            "home": HOME_PLACE_ID,
            }

        self.parsed_shift_ids = set()
        self.workable_shifts  = {}
        self.log = []

        # Attributes that do not persist between states
        self.login_response     = None
        self.logout_response    = None
        self.refresh_response   = None
        self.offered_response   = None        
    
    def loadsession(self, saved_session_json:str):
        saved_session_dict = json.loads(saved_session_json)

        for attribute in ['logged_in', 'login_failed', 'access_token', 'refresh_token', 'place_cache','workable_shifts','log']:
            setattr(self, attribute, saved_session_dict[attribute])
        self.parsed_shift_ids = set(saved_session_dict['parsed_shift_ids'])
    
    def savesession(self):
        saved_session_dict = {}

        for attribute in ['logged_in', 'login_failed', 'access_token', 'refresh_token', 'place_cache','workable_shifts','log']:
            saved_session_dict[attribute] = getattr(self, attribute)
        saved_session_dict['parsed_shift_ids'] = sorted(list(self.parsed_shift_ids))

        return json.dumps(saved_session_dict, indent=4)

    def login(self):
        self.logged_in = False

        if self.login_failed:
            print("Login failed previously. Not attempting to log in again.")
            return

        print("Attempting to log in...")
        login_details = {
            "email": SYFT_EMAIL,
            "grant_type": "password",
            "password": SYFT_PASSWORD
        }

        self.login_response = requests.post(
            url="https://api.syftapp.com/api/v2/users/login", json=login_details, headers=login_headers)

        if self.login_response.ok:
            self.access_token = self.login_response.json()["oauth"]["access_token"]
            self.refresh_token = self.login_response.json()["oauth"]["refresh_token"]
            self.logged_in = True
            print("Login successful.")

        else:
            self.login_failed = True
            print("Login failed; response: ",self.login_response.content.decode())
            self.login_response.raise_for_status()


    def logout(self):
        print("Attempting to revoke OAuth token...")
        logout_body = {
            "token": self.access_token
        }
        logout_headers["authorization"] = "Bearer " + self.access_token

        self.logout_response = requests.post(
            url="https://api.syftapp.com/api/v2/oauth/revoke", json=logout_body, headers=logout_headers)
        self.logout_response.raise_for_status()
        self.logged_in = False


    def refresh(self):
        if not self.logged_in:
            print("Unable to refresh OAuth token. Not logged in.")
            return

        print("Refreshing OAuth token...")
        refresh_body = {
            "refresh_token": self.refresh_token,
        }
        refresh_headers["authorization"] = "Bearer " + self.access_token

        self.refresh_response = requests.post(
            url="https://api.syftapp.com/api/v2/users/refresh", json=refresh_body, headers=refresh_headers)

        if self.refresh_response.ok:
            self.access_token = self.refresh_response.json()["oauth"]["access_token"]
            self.refresh_token = self.refresh_response.json()["oauth"]["refresh_token"]
            print("Refresh successful.")


    def get_offered(self):
        if not self.logged_in:
            print("Unable to get jobs. Not logged in.")
            return

        print("Getting jobs...")
        syftheaders["authorization"] = "Bearer " + self.access_token
        self.offered_response = requests.get(
            url=syft_worker_url, headers=syftheaders)

        if self.offered_response.ok:
            print(len(self.offered_response.json())," jobs returned.")


    def get_place(self, latlng:dict):
        if latlng == "home":
            return self.place_cache["home"]

        key = f"{latlng['latitude']},{latlng['longitude']}"
        if key not in self.place_cache:
            self.place_cache[key] = gmaps.reverse_geocode(latlng=latlng)[0]["place_id"] #possible faliure reverse_geocode returns nothing

        return self.place_cache[key]


    @staticmethod
    def is_shift_workable(job: dict, shift: dict, max_days_from_now:int):
        if (parse(shift["start_time"]) - datetime.now(ZoneInfo("Europe/London"))).days > max_days_from_now:
            return False

        if job["venue_name"] in BLACKLISTED_VENUE_NAMES:
            return False
        return True

    def remove_expired_shifts(self):
        num_removed     = 0
        new_shift_ids   = {str(shift["id"]) for job in self.offered_response.json() for shift in job["shifts"]}

        # Remove shifts from parsed_shifts if they are no longer available.
        for removed_shift_id in self.parsed_shift_ids.difference(new_shift_ids):
            self.parsed_shift_ids.remove(removed_shift_id)
            self.workable_shifts.pop(removed_shift_id, None)
            num_removed+=1

        if num_removed:
            print("Removed ",num_removed," expired shifts.")


    def parse_offered(self, max_outbound=1.5, max_return=1.5, max_days_from_now=12):
        if not self.offered_response:
            print("No offered_response found. Cannot parse.")
            return {}
        assert 'id' in self.offered_response.json()[0], 'offered_response does not contain valid job JSON'

        num_new_shifts = 0
        new_workable_shifts = {}

        for job in self.offered_response.json():
            for shift in job["shifts"]:
                parsedshift = {}

                # If this shift has been already parsed, skip it.
                if str(shift["id"]) in self.parsed_shift_ids:
                    continue
                self.parsed_shift_ids.add(str(shift["id"]))
                if shift["status"] != "offered":
                    continue
                #If this shift is unworkable, skip it.
                if not self.is_shift_workable(job, shift, max_days_from_now):
                    continue

                num_new_shifts+=1

                starttime = parse(shift["start_time"])
                endtime = parse(shift["end_time"])
                parsedshift["duration"]     = (endtime-starttime).total_seconds()/3600
                parsedshift["total_pay"]    = parsedshift["duration"] * job["pay_rate"]["amount"]
                parsedshift["date"]         = starttime.strftime("%a %d %b")
                parsedshift["starttime"]    = starttime.strftime("%I:%M%p")
                parsedshift["endtime"]      = endtime.strftime("%I:%M%p")
                parsedshift["role"]         = job["role"]["title"]+"@"+job["venue_name"]+", "+job["location"]["address"]["city"]

                outbound_routes = gmaps.directions(
                    origin      = "place_id:" + self.get_place("home"),
                    destination = "place_id:" + self.get_place(job["location"]["geo_location"]),
                    arrival_time= starttime,
                    mode        = "transit",
                    alternatives= True
                )
                outbound_commute_times = []
                for route in outbound_routes:
                    departure_tvo           = route["legs"][0]["departure_time"]
                    outbound_departure_time = datetime.fromtimestamp(departure_tvo["value"]).replace(tzinfo=ZoneInfo(departure_tvo["time_zone"]))
                    commute_time_hrs        = (starttime - outbound_departure_time).total_seconds()/3600
                    outbound_commute_times.append(commute_time_hrs)
                min_outbound_departure_tvo = outbound_routes[outbound_commute_times.index(min(outbound_commute_times))]["legs"][0]["departure_time"]
                parsedshift["outbound_departure_time"] = \
                    datetime.fromtimestamp(min_outbound_departure_tvo["value"])\
                    .replace(tzinfo=ZoneInfo(min_outbound_departure_tvo["time_zone"]))\
                    .strftime("%I:%M%p")
                
                if not outbound_commute_times or min(outbound_commute_times) > max_outbound:
                    self.log.append(f'{datetime.now(ZoneInfo("Europe/London")).isoformat()}: R OTL {shift["id"]} {parsedshift["role"]}, {parsedshift["date"]} {parsedshift["outbound_departure_time"]}>{parsedshift["starttime"]}-{parsedshift["endtime"]}>')
                    continue                    

                return_routes = gmaps.directions(
                    origin          = "place_id:" + self.get_place(job["location"]["geo_location"]),
                    destination     = "place_id:" + self.get_place("home"),
                    departure_time  = endtime,
                    mode            = "transit",
                    alternatives    = True
                )
                return_commute_times = []
                for route in return_routes:
                    arrival_tvo         = route["legs"][0]["arrival_time"]
                    return_arrival_time = datetime.fromtimestamp(arrival_tvo["value"]).replace(tzinfo=ZoneInfo(arrival_tvo["time_zone"]))
                    commute_time_hrs    = (return_arrival_time-endtime).total_seconds()/3600
                    return_commute_times.append(commute_time_hrs)

                min_return_arrival_tvo = return_routes[return_commute_times.index(min(return_commute_times))]["legs"][0]["arrival_time"]
                parsedshift["return_arrival_time"] = \
                    datetime.fromtimestamp(min_return_arrival_tvo["value"])\
                    .replace(tzinfo=ZoneInfo(min_return_arrival_tvo["time_zone"]))\
                    .strftime("%I:%M%p")

                if not return_commute_times or min(return_commute_times) > max_return:
                    self.log.append(f'{datetime.now(ZoneInfo("Europe/London")).isoformat()}: R RTL {shift["id"]} {parsedshift["role"]}, {parsedshift["date"]} {parsedshift["outbound_departure_time"]}>{parsedshift["starttime"]}-{parsedshift["endtime"]}>{parsedshift["return_arrival_time"]}')
                    continue                    

                parsedshift["total_commute_time"] = min(outbound_commute_times) + min(return_commute_times)
                
                new_workable_shifts[str(shift["id"])] = parsedshift
                self.workable_shifts = self.workable_shifts | new_workable_shifts

        print("Parsed ",num_new_shifts," shifts, ",len(new_workable_shifts)," new workable shifts found.")
        return new_workable_shifts
        