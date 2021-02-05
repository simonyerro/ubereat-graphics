from __future__ import print_function

import dateparser
import json
import os.path
import pickle
import re
import pandas as pd 
import matplotlib.pyplot as plt
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TWO_TABS = '        '

def _dump(mails, namefile='mails.json'):
    with open(namefile, 'w') as outfile:
        json.dump(mails, outfile)

def _load(namefile='mails.json'):
    with open(namefile) as json_file:
        return json.load(json_file)

def _find_between(s, start, end):
    return (s.split(start))[1].split(end)[0]

def auth():
    """
    Authenticate to the given SCOPES (here the gmail api in read only)
    using a credentials.json. You can get it here: https://console.cloud.google.com/projectselector2
    on the gmail account where you receive the ubereat mails
    """
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_mails(credentials, query, cache=False):
    """
    Retrieve mails matching the given query from your gmail account

    :param credentials: generated from auth() function
    :param query: gmail query to retrieve specific mails
    :param cache: if True, looks for mails.json, a previous json dump of the mails
    """
    if cache:
        try:
            return _load()
        except Exception:
            pass
    service = build('gmail', 'v1', credentials=credentials)
    nextPageToken = None
    mails = []
    while True:
        results = service.users().messages().list(userId='me', q=query, maxResults=100, pageToken=nextPageToken).execute()
        mails += results.get('messages', [])
        if 'nextPageToken' in results:
            nextPageToken = results['nextPageToken']
        else:
            break

    if not mails:
        print('No mails found.')
        return []
    else:
        print('{} mails found'.format(len(mails)))
        print('Retrieving mails...')
        for i, message in enumerate(mails):
            mails[i] = service.users().messages().get(userId='me', id=message['id']).execute()
        _dump(mails)
        print('Done')
        return mails

def parse_mails(mails):
    """
    Data cleasing of the mails previously retrieved

    :param mails: list of mails retrieved by get_mails()
    """
    print('Parsing mails...')
    vals = {'restaurant': [], 'price': [], 'datetime': [], 'reimbursed': [], 'with_tip': []}
    tipped, reimbursed = False, False

    for m in mails:
        if tipped:
            tipped = False
            continue
        elif reimbursed:
            reimbursed = False
            continue

        raw_date = next(item for item in m['payload']['headers'] if item['name'] == 'Received')
        parsed_date = dateparser.parse(" ".join(raw_date['value'].split(TWO_TABS)[1].split(' ')[:-2]))
        price = float(re.search('(\S+?) €', m['snippet']).group(1).replace(',','.'))

        if 'Merci pour votre pourboire' in m['snippet']:
            tipped = True
            restaurant = _find_between(m['snippet'], 'votre nouvelle facture pour ', '.')
        elif 'Remboursement' in m['snippet']:
            reimbursed = True
            restaurant = _find_between(m['snippet'], 'votre facture pour ', '.')
        else:
            restaurant = _find_between(m['snippet'], 'Voici votre facture pour ', '.')

        vals['restaurant'].append(restaurant)
        vals['price'].append(price)
        vals['datetime'].append(parsed_date)
        vals['reimbursed'].append(reimbursed)
        vals['with_tip'].append(tipped)

    data = {
        "restaurant": vals["restaurant"],
        "price": vals["price"],
        "datetime": vals["datetime"],
        "reimbursed": vals["reimbursed"],
        "with_tip": vals["with_tip"]
    }
    print('Done')
    return pd.DataFrame(data)

if __name__ == "__main__":
    query = 'from:uber.france@uber.com subject:commande'

    mails = parse_mails(
                get_mails(
                    auth(), query, cache=True))

    plt.plot(mails["datetime"],mails["price"])
    plt.show()