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
# from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from post_note import *
from set_query_filters import *
import os
import time
from append_json import *
from store_stackjoin import *
from dotenv import load_dotenv, find_dotenv
from extract_note_id_to_stackjoinadd import *
from query_user_display_name import *

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

public_key = PublicKey.from_npub(os.environ.get("PUBLIC_KEY"))
private_key = PrivateKey.from_nsec(os.environ.get("PRIVATE_KEY"))

# HASHTAG = "stackjoin"

def query_nostr_relays(type_of_query, query_term, since=0):
  if type_of_query != "individual_event":
    event_id = ""
  request, filters, subscription_id = set_query_filters(type_of_query=type_of_query, query_term=query_term, since=since)

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
  time.sleep(20) # allow the messages to send

  relay_manager.close_connections()

  return relay_manager.message_pool

def stackchainsiggy_nostr(start_time_for_first_run = 0):
  print("\n*****\n"+datetime.now().isoformat()+": running stackchainsiggy_nostr")

  with open('last_time_checked.json', 'r') as f:
    times_checked = json.load(f)
    # last_time_checked = int(times_checked[0]['checked_time'])
    if start_time_for_first_run != 0:
      last_time_checked = start_time_for_first_run
      print(f"checking from datetime ISO {datetime.fromtimestamp(start_time_for_first_run).isoformat()}")
      hashtag = "stackjoin"
    else:
      if times_checked[0]["hashtag_checked"] == "stackjoin":
        hashtag = "stackjoinadd"
      else: 
        hashtag = "stackjoin"
      if times_checked[1]["hashtag_checked"] == hashtag:
        print("if")
        last_time_checked = times_checked[2]["checked_time"]
        print(f'last time checked ISO is {times_checked[1]["checked_time_iso"]}. Now checking for {hashtag}')
      else:
        print("else")
        last_time_checked = times_checked[1]["checked_time"]
        print(f'last time checked ISO is {times_checked[2]["checked_time_iso"]}. Now checking for {hashtag}')
    
  # hashtag = "stackjoinadd"

  message_pool_relay_manager_hashtag = query_nostr_relays(since=last_time_checked, type_of_query="hashtag", query_term=hashtag)

  while message_pool_relay_manager_hashtag.has_events():
    event_msg = message_pool_relay_manager_hashtag.get_event()
    print("\n\n___________NEW_EVENT__________")
    print(f"event.json: {event_msg.event.json}")
    has_hashtag = False
    for tag in event_msg.event.json[2]["tags"]:
      if "t" in tag:
        print("event tag found")
        for item in tag:
          if item == hashtag:
            print(f"{hashtag} hashtag found")
            if event_msg.event.json[0] == "EVENT":
              print(f"\n>> Poster's profile on snort.social: https://snort.social/p/{PublicKey.hex_to_bech32(event_msg.event.json[2]['pubkey'], 'Encoding.BECH32')}")
              print(f">> Event on snort.social: https://snort.social/e/{PublicKey.hex_to_bech32(event_msg.event.json[2]['id'], 'Encoding.BECH32')}")
            has_hashtag = True
    # additional check to see if event is already in json, hence already responded to
    new_event = True
    with open("events.json", "r") as f:
      events = json.load(f)
      for event in events:
        if event_msg.event.json[2]["id"] == event[2]["id"]:
          new_event = False
          print("found event on json, skipping append_json and posting")
    if new_event == True:
      print("didn't find event on json, moving forward to append_json and posting")
    if has_hashtag == True and new_event == True:
      append_json(event_msg = event_msg.event.json)
      print('starting store stackjoin')
      if hashtag == "stackjoinadd":
        query_term = extract_note_id_to_stackjoinadd(event_msg)
        stackjoinadd_reporter = " [stackjoinadd_reporter: "+query_user_display_name(event_msg.event.json[2]['pubkey'])+" - npub "+event_msg.event.json[2]["pubkey"]
        stackjoinadd_tweet_message = " - message: "+event_msg.event.json[2]["content"] + "]"
        message_pool_relay_manager_stackjoinadd = query_nostr_relays(since=0, type_of_query="individual_event", query_term=query_term)
        while message_pool_relay_manager_stackjoinadd.has_events():
          event_msg = message_pool_relay_manager_stackjoinadd.get_event()
        store_stackjoin(event_msg.event.json, datetime.fromtimestamp(event_msg.event.json[2]['created_at']).isoformat(), stackjoinadd_reporter=stackjoinadd_reporter, stackjoinadd_tweet_message=stackjoinadd_tweet_message)
      else:
        store_stackjoin(event_msg.event.json, datetime.fromtimestamp(event_msg.event.json[2]['created_at']).isoformat())
      post_note(private_key, "content todo", [["e",event[2]['id']]])
  
  # updating last time checked for new notes
  with open('last_time_checked.json', 'r+') as f:
    times_checked = json.load(f)
    times_checked.reverse()
    times_checked.append({"checked_time":datetime.now().timestamp(), "checked_time_iso": datetime.now().now().isoformat(), "number_of_checks":times_checked[len(times_checked)-1]['number_of_checks']+1, "hashtag_checked": hashtag})
    if len(times_checked) > 20:
      times_checked.pop(0)
    times_checked.reverse()
    f.seek(0)
    f.truncate(0)
    f.write(json.dumps(times_checked, indent=4))

  print("finished running stackchainsiggy_nostr")

if __name__ == "__main__":

  #running main function once
  stackchainsiggy_nostr(start_time_for_first_run=int(datetime.now().timestamp()))

  scheduler = BlockingScheduler()
  scheduler.add_job(stackchainsiggy_nostr, 'interval', seconds=90)
  print('\nstarting scheduler')
  scheduler.start()