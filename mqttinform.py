import paho.mqtt.client as mqtt


class MQTTInform():
    def __init__(self, hostname):
        self.client = mqtt.Client()
        self.hostname = hostname
        self.client.connect(self.hostname,1883,60)

    def Inform(self, slot, user, freq):
        topic = "kiwisdr/"+str(slot)
        self.client.publish(topic, str(user) + " " + str(freq));



# client.disconnect();