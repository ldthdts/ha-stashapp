# Stash for Home Assistant

A custom integration that connects Home Assistant to a [Stash](https://stashapp.cc) server. It reports library statistics as sensors, provides image feeds that each show a random image matching their own tag filter, and offers services to pick random images or scenes and to start a library scan.

## Installation (HACS)

1. In HACS, open **Custom repositories** and add `https://github.com/ldthdts/ha-stashapp` with category **Integration**.
2. Search for **Stash** in HACS and download it.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and choose **Stash**.

## Configuration

- **URL**: the address of your Stash server, for example `http://192.168.1.10:9999`.
- **API key**: only needed when authentication is enabled in Stash. Create one in Stash under **Settings → Security**.

If the API key is later rejected, Home Assistant starts a re-authentication flow.

## Entities

| Entity | Description |
| --- | --- |
| Scenes, Images, Galleries, Performers, Studios, Tags, Scene markers | Object counts |
| Scenes played, Total play count, Total O count | Playback statistics |
| Scenes size, Images size | Library size in GB |
| Scenes duration, Total play duration | Durations in hours |
| Active jobs | Stash jobs that are queued or running |
| Version | Stash server version (diagnostic) |
| One entity per image feed | Image entity showing a random image for that feed (see [Image feeds](#image-feeds)) |

## Image feeds

You can add as many image feeds as you like. Each feed is an image entity with its own tag filter and optional auto refresh interval, so you can have, for example, one feed for a favourite tag and another for a different tag.

To add a feed, open the Stash integration, choose **Add image feed**, and fill in:

- **Name**: the feed name. The entity is named `Stash <name>`.
- **Tags**: Stash tag IDs. A random image must have at least one of them. Leave empty for any image.
- **Auto refresh (minutes and seconds)**: optional. How often the feed picks a new image on its own, for example 5 minutes and 30 seconds. Leave both fields empty to turn it off; the `stashapp.refresh_feed` service still works. The minimum is 10 seconds and the maximum is one week.

Each feed can be edited later from its entry in the integration page, and changes take effect straight away.

## Services

### `stashapp.random_image`

Picks a random image and returns its details. It does not update any entity. To display images, use an image feed.

```yaml
action: stashapp.random_image
data:
  tags: ["12", "34"]
response_variable: picked
```

Response: `id`, `title`, `image_url`.

### `stashapp.refresh_feed`

Picks a new random image for one or more image feed entities right away.

```yaml
action: stashapp.refresh_feed
target:
  entity_id: image.stash_favourites
```

### `stashapp.random_scene`

Picks a random scene and returns its details. Response: `id`, `title`, `url`, `screenshot_url`.

### `stashapp.scan_library`

Starts a full metadata scan. Response: `job_id`.

### Options

- `config_entry_id`: only needed when more than one Stash server is configured.
- `tags`: a list of Stash tag IDs. Results must have at least one of them. Find tag IDs in the Stash tag page URL (`/tags/<id>`).

## Example automation

```yaml
automation:
  - alias: Show a random Stash image every morning
    triggers:
      - trigger: time
        at: "07:00:00"
    actions:
      - action: stashapp.random_image
    mode: single
```

Feed entities can be shown on a dashboard with a picture entity card.

## Development

Run the unit tests from the repository root in a Python 3.12+ environment with Home Assistant installed:

```bash
python -m unittest discover -v
```
