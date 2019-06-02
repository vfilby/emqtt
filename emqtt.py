#!/usr/bin/env python3
import asyncio
import email
import logging
import os
import signal
import time
from datetime import datetime
from email.policy import default

from aiosmtpd.controller import Controller
from paho.mqtt import publish


defaults = {
    'SMTP_PORT': 1025,
    'MQTT_HOST': 'localhost',
    'MQTT_PORT': 1883,
    'MQTT_USERNAME': '',
    'MQTT_PASSWORD': '',
    'MQTT_TOPIC': 'emqtt',
    'MQTT_PAYLOAD': 'ON',
    'MQTT_RESET_TIME': '300',
    'MQTT_RESET_PAYLOAD': 'OFF',
    'SAVE_ATTACHMENTS': 'True',
    'SAVE_ATTACHMENTS_DURING_RESET_TIME': 'False',
    'SAVE_RAW_MESSAGES': 'False',
    'DEBUG': 'False'
}
config = {
    setting: os.environ.get(setting, default)
    for setting, default in defaults.items()
}

# Boolify
for key, value in config.items():
    if value == 'True':
        config[key] = True
    elif value == 'False':
        config[key] = False

level = logging.DEBUG if config['DEBUG'] else logging.INFO

log = logging.getLogger('emqtt')
log.setLevel(level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Log to console
ch = logging.StreamHandler()
ch.setFormatter(formatter)
log.addHandler(ch)


####
# Base class for user-defined plugins
class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # list where plugins can be registered later.
            cls.plugins = []
        else:
            # This must be a plugin implementation, which should be
            # registered. Simply appending it to the list is all that's
            # needed to keep track of it later.
            cls.plugins.append(cls)


class EmailProcessor:
    """
    Super class for plugins that can process email messages to customize
    the MQTT topic, payload, reset-time as well as take any actions on
    attachments
    
    TODO: Figure out how to handle:
      * reset time (-1 for no reset)
      * Attachments
      * how to hook into email addresses.
    
    Needs to expose the following properties:
     - topic
     - payload
    """
    def __init__(self, ):
      self._payload = "YES"
      self._topic = "no-topic"
    
    @property
    def payload(self):
      return self._payload
  
    @payload.setter
    def payload( self, val ):
      self._payload = val
    
    __metaclass__ = PluginMount

class mqtt_packet:
  def __init__(self):
    self.topic = config['MQTT_TOPIC']
    self.reset_time = config['MQTT_RESET_TIME']
    self.payload = config['MQTT_PAYLOAD']

class EMQTTHandler:
    def __init__(self, loop):
        self.loop = loop
        self.reset_time = int(config['MQTT_RESET_TIME'])
        self.handles = {}
        self.quit = False
        signal.signal(signal.SIGTERM, self.set_quit)
        signal.signal(signal.SIGINT, self.set_quit)
        if config['SAVE_ATTACHMENTS']:
            log.info('Configured to save attachments')


        
    def get_mqtt_message( self, msg, config ):
        
        response = mqtt_packet()
        
        response.topic = '{}/{}'.format(
          response.topic, 
          msg['from'].replace('@', '')
        )
        
        return response
        

    async def handle_DATA(self, server, session, envelope):
        log.debug('Message from %s', envelope.mail_from)
        email_message = email.message_from_bytes(
          envelope.original_content, 
          policy=default
        )
        
        log.debug(
            'Message data (truncated): %s',
            email_message.as_string()[:250]
        )
        
        # If enabled this saves the message content as a string to disk
        # this is only useful for debugging or recording messages to 
        # be used in tests
        if config['SAVE_RAW_MESSAGES']:
            msg_filename = email_message['subject']
            log.debug( "Saving message content: %s", msg_filename )
            file_path = os.path.join('messages', msg_filename)
            with open(file_path, 'w+') as f:
                f.write( email_message.as_string() )
        
        mqtt_msg = self.get_mqtt_message( email_message, config )
        self.mqtt_publish( mqtt_msg.topic, mqtt_msg.payload )

        # Save attached files if configured to do so.
        if config['SAVE_ATTACHMENTS'] and (
                # Don't save them during rese time unless configured to do so.
                mqtt_msg.topic not in self.handles
                or config['SAVE_ATTACHMENTS_DURING_RESET_TIME']):
            log.debug(
                'Saving attachments. Topic "%s" aldready triggered: %s, '
                'Save attachment override: %s',
                    mqtt_msg.topic,
                    mqtt_msg.topic in self.handles,
                    config['SAVE_ATTACHMENTS_DURING_RESET_TIME']
            )
            for att in email_message.iter_attachments():
                # Just save images
                if not att.get_content_type().startswith('image'):
                    continue
                filename = att.get_filename()
                image_data = att.get_content()
                file_path = os.path.join('attachments', filename)
                log.info('Saving attached file %s to %s', filename, file_path)
                with open(file_path, 'wb') as f:
                    f.write(image_data)
        else:
            log.debug('Not saving attachments')
            log.debug(self.handles)


        # Cancel any current scheduled resets of this topic
        if mqtt_msg.topic in self.handles:
            self.handles.pop(mqtt_msg.topic).cancel()

        if self.reset_time:
            # Schedule a reset of this topic
            self.handles[mqtt_msg.topic] = self.loop.call_later(
                self.reset_time,
                self.reset,
                mqtt_msg.topic
            )
        return '250 Message accepted for delivery'

    def mqtt_publish(self, topic, payload):
        log.info('Publishing "%s" to %s', payload, topic)
        try:
            publish.single(
                topic,
                payload,
                hostname=config['MQTT_HOST'],
                port= int( config['MQTT_PORT'] ),
                auth={
                    'username': config['MQTT_USERNAME'],
                    'password': config['MQTT_PASSWORD']
                } if config['MQTT_USERNAME'] else None
            )
        except Exception as e:
            log.exception('Failed publishing')

    def reset(self, topic):
        log.info(f'Resetting topic {topic}')
        self.handles.pop(topic)
        self.mqtt_publish(topic, config['MQTT_RESET_PAYLOAD'])

    def set_quit(self, *args):
        log.info('Quitting...')
        self.quit = True


if __name__ == '__main__':
    log.debug(', '.join([f'{k}={v}' for k, v in config.items()]))

    # If there's a dir called log - set up a filehandler
    if os.path.exists('log'):
        log.info('Setting up a filehandler')
        fh = logging.FileHandler('log/emqtt.log')
        fh.setFormatter(formatter)
        log.addHandler(fh)

    loop = asyncio.get_event_loop()
    c = Controller(EMQTTHandler(loop), loop, '0.0.0.0', config['SMTP_PORT'])
    c.start()
    log.info('Running')
    try:
        while not c.handler.quit:
            time.sleep(0.5)
        c.stop()
    except:
        c.stop()
        raise
