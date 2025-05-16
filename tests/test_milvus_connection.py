from pymilvus import connections
connections.connect('default', host='192.168.144.129', port='19530')
print(connections.has_connection("default"))