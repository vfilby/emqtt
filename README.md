
|  | Status |
|-------|--------|
| **Main** | [![Build Status](https://travis-ci.com/vfilby/emqtt.svg?branch=master)](https://travis-ci.com/vfilby/emqtt) |
| **Beta** | [![Build Status](https://travis-ci.com/vfilby/emqtt.svg?branch=beta)](https://travis-ci.com/vfilby/emqtt) |

# emqtt

Receive emails and publish to MQTT. Super simple stuff. Topic will be `<configurable_prefix>/<sender_email.replace('@', '')>`.

I needed this to make my D-Link camera's motion sensor functionality useful.
Available actions on the camera are to send an email or upload an image to an FTP..
This script makes it easier to integrate into automation systems.

It's based on aiosmtpd and paho-mqtt.

I made a docker image because like any hipster dev I like docker. At least it's based on alpine so there's that.

Protip: `docker exec emqtt find attachments -type f -ctime +20 -delete`




## Setup / Installation 

###Run it

1. Create venv and activate it. Or don't.

1. `pip install -r requirements.txt`.

1. Give it some env vars. These are the defaults so omit whatever looks good.
   * SMTP_PORT=1025
   * MQTT_HOST=localhost
   * MQTT_PORT=1883
   * MQTT_USERNAME=""
   * MQTT_PASSWORD=""
   * MQTT_TOPIC=emqtt
   * MQTT_PAYLOAD=ON
   * MQTT_RESET_TIME=300
   * MQTT_RESET_PAYLOAD=OFF
   * SAVE_ATTACHMENTS=True
   * SAVE_ATTACHMENTS_DURING_RESET_TIME=False
   * DEBUG=False

1. Go.
```
$ python emqtt.py
2017-11-08 22:36:27,658 - root - INFO - Running
```

### Run it in docker

```
$ docker build -t emqtt .
$ docker run -d \
    --name emqtt \
    --net host \
    --restart always \
    -e "MQTT_USERNAME=mqtt" \
    -e "MQTT_PASSWORD=mqtt" \
    -e "DEBUG=True" \
    -v /etc/localtime:/etc/localtime:ro \
    -v $PWD/log:/emqtt/log \
    -v $PWD/attachments:/emqtt/attachments \
    emqtt
```

## Plugins

You can put customize the mqtt messages based on custom scripts. These scripts need to be placed in the configured `plugins/` direction and will be loaded when emqtt starts. Each file should contain a single class and the name of the class should match the filename (even if this isn't strictly enforced at this point).

Example:

```python
import logging
from emqtt.plugins import EmailProcessor

log = logging.getLogger('test_email_plugins_TestPlugin1')

class test_email_plugins_TestPlugin1(EmailProcessor):
    def apply_to_sender( self, sender ):
        log.debug( sender )
        return sender == "AAA IPCamera <cam4_c2@l.filby.co>"

    def mqtt_message( self, email_message ):
        response = mqtt_packet()
        response.topic = '{}/{}'.format(
          response.topic, 
          "test_topic"
        )
        return response
```

## Development

### Debugging Tests

Insert `import pdb; pdb.set_trace()` into the code to drop into the debugger.

Execute tests with `python3 -m pytest --pdb tests/`



 