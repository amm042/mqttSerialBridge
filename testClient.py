import paho.mqtt.client as mqtt
import time
import os
import datetime
import sys

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("test/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print("rcv: "+msg.topic+" "+str(msg.payload))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

#client.connect_async("amm042", 9999, 60)
port = 1883
#port = 9999
if ( client.connect("localhost", port, 60) != mqtt.MQTT_ERR_SUCCESS ):
    print("Failed to connect.")
    exit(-1)


if len(sys.argv) > 1:
    cnt = int(sys.argv[1])

else:
    cnt = 16

#client.connect("amm042", 9999, 60)
client.loop_start()
time.sleep(5)
print("Sending {} messages".format(cnt))
topic ='test/{}'.format(os.getpid())
for i in range(cnt):

    msg = 'the value is {} at {}'.format(i, datetime.datetime.now())
    print("pub: {} - {}".format(topic, msg))
    client.publish(topic, msg, qos=2)
    time.sleep(0.15)
time.sleep(30)
client.disconnect()
time.sleep(1)
client.loop_stop()

print("Googbye.")
