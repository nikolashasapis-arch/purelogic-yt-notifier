# purelogic upload notifier
every 15 minutes, checks the PureLogic, PureBusiness and PureSports YouTube feeds and posts new videos into the matching uploads channel in the PureLogic Community discord, pinging that channel's role.

- channels: edit `channels.json` (handle or UC channel id)
- discord webhooks: the `WEBHOOKS` repo secret
- run it now: Actions tab -> "youtube uploads to discord" -> Run workflow

## switches
`settings.json` turns the upload and milestone posts on/off. the join/leave log (`members.py`) runs every time and posts in #joins-and-leaves.
