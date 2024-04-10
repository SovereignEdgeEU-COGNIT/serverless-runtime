# Serverless Runtime as a Service

This folder contains the system unit generated in order to run the Serverless Runtime as a background service. 

To create the customized service, we need to create a new systemd service in `/etc/systemd/system/`. The following is the service that will run the SR: `cognit_sr_su.service`

```
[Unit]
Description=Serverlerss Runtime service.

[Service]
TimeoutStartSec=5
ExecStart=/bin/bash -c 'cd /root/serverless-runtime/ && source serverless-env/bin/activate && cd app/ && python3 main.py'

[Install]
WantedBy=multi-user.target
```

Once the service is created, we need to reload the daemon:

```
sudo systemctl daemon-reload
```

After that, we can enable and start the Serverless Runtime service:

```
sudo systemctl enable cognit_sr_su.service
sudo systemctl start cognit_sr_su.service
```

To stop the service, execute the following:

```
sudo systemctl stop cognit_sr_su.service
```