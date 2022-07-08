# Autoflex

A web app that alerts you when new jobs are added to Syft.

Uses the Google Maps Directions API to calculate commute time.

## Usage

1. Create a file named `autoflex_secrets.py` and populate it with the following variables.  
Include a copy of this file when deploying each of the Cloud Functions in step 2 and 3.

```python
# The name of an existing Google Cloud Storage bucket accessible to you.
BUCKET_NAME:str = ""

# Names of JSON file blobs which will be created in BUCKET_NAME which store subscription and session data, respectively. Keeping these defaults is recommended.
SUBSCRIPTIONS_FILE_NAME:str:   = "subscriptions.json"
SESSION_FILE_NAME:str          = "session.json"

# Keys for the Web Push service, generated using:
# https://web.dev/push-notifications-subscribing-a-user/#how-to-create-application-server-keys
vapidKeys:dict[str,str] = {
    "publicKey" :"",
    "privateKey":""
    }

# An email address to send VAPID error messages to, beginning with "mailto:"
VAPID_MAILTO:str    = ""

# An API key for the Google Maps API.
GMAPS_API_KEY:str   = ""

# The Google Maps Place ID of your "home" destination used in commute time calculations.
HOME_PLACE_ID:str   = ""

# Your Syft login details.
SYFT_EMAIL:str      = ""
SYFT_PASSWORD:str   = ""

# Names of blacklisted venues you don't want to parse.
BLACKLISTED_VENUE_NAMES: list[str] = []


###########################################################################
# The following variables need to be obtained by emulating the Syft app on Android/iOS and intercepting its HTTP requests. HTTP Toolbox is recommended for doing this.
# 
# Only the syft_worker_url is necessary, and the headers can be left as blank dictionaries; however, populating the headers will more closely mimic a real Syft app.
###########################################################################

# Your Worker URL for getting Offered jobs from the Syft API. Replace XXXXXX with your worker number.
syft_worker_url:str = "https://api.syftapp.com/api/v2/workers/XXXXXX/upcoming_jobs?status=offered"

# The HTTP headers when login, logout, refresh, and upcoming_jobs requests are made to the Syft API. These need to be obtained by listening to HTTP requests that a real Syft app makes. 
login_headers:dict[str,str]   = {}
logout_headers:dict[str,str]  = {}
refresh_headers:dict[str,str] = {}
syftheaders:dict[str,str]     = {}
```


2. Deploy `periodicQuery.py` as a Pub/Sub triggered Cloud Function, and use Cloud Scheduler publish a message to its triggering topic your desired frequency. Lines 65-69 in `periodicQuery.py` contain configurable fuzzing settings.

3. Deploy `registerSubscription.py` as a public HTTP-triggered Cloud Function. Make note of its invocation URL.

4. In `/firebase/public/`, create `autoflex_secrets.js` and populate it with the following variables:

```javascript
// The invocation URL for registerSubscription, from step 3.
top.subscriptionURL = ""

// The public key from the vapidKeys dictionary in the autoflex_secrets.py file.
top.applicationServerKey = ""
```

5. Deploy everything in `/firebase/public/` to your hosting service of choice, e.g. Firebase or GitHub Pages.

6. After deploying, visit the website, ensuring notification permissions are on for your browser. You should now get notifications whenever new shifts that meet the filtering parameters defined at the top of `periodicQuery.py` are added to Syft.