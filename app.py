import connexion
import datetime
import yaml as yaml
from connexion import NoContent
import logging.config
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json
from threading import Thread
from pykafka import KafkaClient
import pykafka
from flask_cors import CORS, cross_origin

sched = BackgroundScheduler()

with open ('app_conf.yml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('log_conf.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

def get_booking_stat():
    logger.info('Request has started')

    try:
        with open(app_config['datastore']['filename'], 'r') as file:
            f = json.load(file)
            dentist_reading = f['Dentist_Reading']
            doctor_reading = f['Doctor_Reading']
            date = f['Date']
            context = {
                'num_dentist_reading': dentist_reading,
                'num_doctor_reading': doctor_reading,
                'timestap': date
            }
            logger.debug(context)
        logger.info('Request has been completed')
        return context, 200
    except:
        logger.error('data.json does not exist')
        return 400

def populate_stats():
    '''Periodically update stats'''
    logger.info('Starting periodic processing')
    current_datetime = datetime.datetime.now()
    current = current_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        f = open(app_config['datastore']['filename'])
    except:
        f = open(app_config['datastore']['filename'], 'w+')
        stats = {'Dentist_Reading': 0, 'Doctor_Reading': 0, 'Date': current}
        with open(app_config['datastore']['filename'], 'w') as file:
            json.dump(stats, file)
        print('JSON file not found. Creating new JSON file')

    with open(app_config['datastore']['filename'], 'r') as file:
            f = json.load(file)
            old_date = f['Date']

    headers = {
        "Content-type": "application/json"
    } 

    parameters = {
        "startDate": old_date,
        "endDate": current
    } 
    r = requests.get(app_config['eventstore']['url'] + '/doctor',
         params=parameters, headers=headers)

    if r.status_code != 200:
        logger.error('Could not get 200 response code')

    doctor_content = json.loads(r.content)
    doctor_count = len(doctor_content)

    r = requests.get(app_config['eventstore']['url'] + '/dentist',
         params=parameters, headers=headers)

    if r.status_code != 200:
        logger.error('Could not get 200 response code')

    dentist_content = json.loads(r.content)
    dentist_count = len(dentist_content)

    total_count = dentist_count + doctor_count

    logger.info('{0} events received!'.format(total_count))

    with open(app_config['datastore']['filename'], 'r') as file:
            f = json.load(file)
            old_date = f['Date']
            old_dentist_reading = f['Dentist_Reading']
            old_doctor_reading = f['Doctor_Reading']
            old_total_count = old_dentist_reading + old_doctor_reading

            new_dentist_count = dentist_count + old_dentist_reading
            new_doctor_count = doctor_count + old_doctor_reading 
            new_count = total_count + old_total_count
            logger.debug('{0} events received, events recieved is now {1} events since {2}'.format(total_count, new_count, old_date))

            file.close()
    with open(app_config['datastore']['filename'], 'w+') as file:
            new_json = {'Dentist_Reading': new_dentist_count, 'Doctor_Reading': new_doctor_count, 'Date': current}
            json.dump(new_json, file)
            file.close()

    logger.info('Periodic preocssing has ended')

def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats, 'interval', seconds=app_config['scheduler']['period_sec'])
    sched.start()

app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("openapi.yml")
CORS(app.app)
app.app.config['CORS_HEADERS'] = 'Content-Type'

logger = logging.getLogger('basicLogger')

if __name__ == "__main__":
    init_scheduler()
    app.run(port=8100, use_reloader=False)