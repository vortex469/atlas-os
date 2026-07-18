# Atlas Core

Atlas Core is the central API for Atlas OS.

## Address

- API: http://atlas-host:8643
- Documentation: http://atlas-host:8643/docs
- Health: http://atlas-host:8643/health

## Service Management

Start:

    systemctl start atlas-core

Stop:

    systemctl stop atlas-core

Restart:

    systemctl restart atlas-core

Status:

    systemctl status atlas-core

Logs:

    journalctl -u atlas-core -f
