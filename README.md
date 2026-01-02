# romm-gog-custodian

Unofficial tooling designed to bridge some gaps with Romm libraries as well as provide a way to automatically manage
qbittorrent downloads.

## Notable Features

- Automatically import games from qBittorrent to your Romm library.
- Renaming based on api data to improve Romm matching.
- Game library cleanup and organization.
- Refresh library file hashes when games are updated.
- Configurable logging with log rotation
- Customizable settings via `config/config.cfg`
- Periodic execution with configurable wait time

## Notes

You will need to build your own pipeline for your torrent downloads. I recommend using AutoBrr with an RSS feed to
curate your torrents.

This would look something like:

``` 
* Autobrr
    * Setup a Indexer (RSS Feed)
    * Setup qbittorrent as a download client.
    * Create a filter, with your indexers with the action type of "qBittorrent".
        * Specify the Category as: gog
Once the torrents are done downloading and no longer seeding, they will be moved to the Romm library on the next run.
```

## How to Run

### Docker Environment

1. **Pull and run the container:**
   ```
   docker run -d \
     --name romm-gog-custodian \
     -v /path/to/your/config:/app/config \
     -v /path/to/your/cache:/app/cache \
     -v /path/to/your/logs:/app/logs \
     -v /path/to/your/library:/data/library \
     -v /path/to/your/torrents:/data/torrent \
     ghcr.io/maus-me/romm-gog-custodian:latest
   ```

## Logging

Logs are written to the file specified by `log_file_path`. The log file will automatically rotate when it reaches 5MB,
keeping up to 5 backup files.

## Roadmap

- [ ] Add support for more game platforms
- [ ] Improve minimum game size check per console type
- [ ] Add ClamAV support for virus scanning
- [ ] Add branch for development and stable
- [X] Add library scanning functionality

