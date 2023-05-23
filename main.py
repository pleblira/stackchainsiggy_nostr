import json
import ssl
import time
from python_nostr_package.nostr import RelayManager
from python_nostr_package.nostr import PublicKey, PrivateKey
# from python_nostr import RelayManager
# from python_nostr import PublicKey, PrivateKey
# from nostr.relay_manager import RelayManager
# from nostr.key import PublicKey
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from post_note import *
from set_query_filters import *
import os
import time
from append_json import *
from store_stackjoin import *
from dotenv import load_dotenv, find_dotenv

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

public_key = PublicKey.from_npub(os.environ.get("PUBLIC_KEY")).hex()
private_key = PrivateKey.from_nsec(os.environ.get("PRIVATE_KEY")).hex()


def timer(func):
    def wrapper():
        before = time.time()
        func()
        print("check_json_for_new_notes_and_reply function took: ", time.time() - before, "seconds")    
    return wrapper

def main(public_key, empty_json_since=0, since=0):
  request, filters, subscription_id = set_query_filters(public_key, since)

  print(request, filters)
  relay_manager = RelayManager()
  with open('relay_list.txt', 'r') as f:
    for line in f:
        relay_manager.add_relay(line.strip())
  relay_manager.add_subscription(subscription_id, filters)
  relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE}) # NOTE: This disables ssl certificate verification
  time.sleep(1.25) # allow the connections to open
  message = json.dumps(request)
  relay_manager.publish_message(message)
  time.sleep(1) # allow the messages to send

  while relay_manager.message_pool.has_events():
    # print(f"since is {since}")
    event_msg = relay_manager.message_pool.get_event()
    print("\n\n___________NEW_EVENT__________")
    # print(f"{event_msg}\n")
    # print(event_msg.event.content)
    # print(f"created_at: {event_msg.event.created_at}")
    # print(f"created at ISO: {datetime.datetime.fromtimestamp(event_msg.event.created_at)}")
    # print(f"event.tags: {event_msg.event.tags}")
    # print(f"event.kind: {event_msg.event.kind}")
    # print(event_msg.event.public_key)
    # print(event_msg.event.signature)
    # print(f"event.id: {event_msg.event.id}")
    # print(f"event.json: {event_msg.event.json}")
    # print(f"event.json[2]['id']: {event_msg.event.json[2]['id']}")

    append_json(event_msg = event_msg.event.json)
    
    if since == empty_json_since:
      with open('events.json', 'r+') as f:
        events = json.load(f)
        events.reverse()
        f.seek(0)
        f.write(json.dumps(events, indent=4))

  return relay_manager
 
  # relay_manager.close_connections()

def close_connections(relay_manager):
  relay_manager.close_connections()

@timer
def check_json_for_new_notes_and_reply():
  print("running check_json_for_new_notes")

  with open('last_time_checked.json', 'r') as f:
    times_checked = json.load(f)
    last_time_checked = times_checked[len(times_checked)-1]['checked_time']
 
  with open('events.json', 'r') as f:
    events = json.load(f)
    for event in events:
      # default functionality
      if datetime.fromisoformat(event[3]['datetime_event_was_queried']).timestamp() > last_time_checked:
      # for grabbing individual events
      # if datetime.fromisoformat(event[3]['datetime_event_was_queried']).timestamp() > 0:
        print("new event found on json")
        post_note(private_key, "content todo", [["e",event[2]['id']]])
        print('starting store stackjoin')
        store_stackjoin(event, datetime.fromtimestamp(event[2]['created_at']).isoformat())
  
  with open('last_time_checked.json', 'r+') as f:
    times_checked = json.load(f)
    times_checked.append({"checked_time":datetime.now().timestamp(), "number_of_checks":times_checked[len(times_checked)-1]['number_of_checks']+1})
    if len(times_checked) > 5:
      # times_checked[:len(times_checked)-5] = ""
      times_checked.pop(0)
    f.seek(0)
    f.truncate(0)
    f.write(json.dumps(times_checked, indent=4))

if __name__ == "__main__":
  # if not os.path.exists('events.json'):
  #   with open('events.json','w') as f:
  #     pass
  with open('events.json','w') as f:
    pass
  if os.stat('events.json').st_size == 0:
    with open('events.json','w') as f:
      f.write("[]")
  with open('events.json','r') as f:
    events = json.load(f)
    if events == []:
      empty_json_since = int(datetime.now().timestamp()-100000)
      since = empty_json_since
    else:
      since = int(datetime.fromisoformat(events[-1+len(events):][0][3]['datetime_event_bug fiwas_queried']).timestamp())
      empty_json_since = 0

  relay_manager = main(public_key, since=since, empty_json_since=empty_json_since)
  
  with open('last_time_checked.json', 'w') as f:
    pass
  with open('last_time_checked.json','w') as f:
    f.write("[]")
    times_checked = []
    times_checked.append({"checked_time": datetime.now().timestamp(), "number_of_checks":0})
    f.seek(0)
    f.write(json.dumps(times_checked, indent=4))

  #running check_json once
  time.sleep(1)
  check_json_for_new_notes_and_reply()

  scheduler = BackgroundScheduler()
  scheduler.add_job(check_json_for_new_notes_and_reply, 'interval', seconds=5)
  print('\nstarting scheduler')
  scheduler.start()

  try:
    # This is here to simulate application activity (which keeps the main thread alive).
    while True:
        with open('events.json', 'r') as f:
          events = json.load(f)
          last_queried_event_datetime = int(datetime.fromisoformat(events[len(events)-1][3]['datetime_event_was_queried']).timestamp())
        # print(f"last queried event datetime {last_queried_event_datetime}")
        # quit()
        time.sleep(600)
        print('closing connections to relays')
        close_connections(relay_manager)
        time.sleep(5)
        print('restarting connection on relay manager')
        relay_manager = main(public_key, since=last_queried_event_datetime)
        print('resuming')
  except (KeyboardInterrupt, SystemExit):
      # Not strictly necessary if daemonic mode is enabled but should be done if possible
      scheduler.shutdown()