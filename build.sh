COMPOSE_DIR=~/Projects/home-server/home.local/docker/compose/services/cs2server

# map-images/ is bind-mounted from $COMPOSE_DIR/panel/map-images (not baked into the image, so
# thumbnails can be dropped in without a rebuild) - keep that directory synced with this repo's
# copy on every deploy, otherwise newly-added images silently don't show up in the panel.
mkdir -p "$COMPOSE_DIR/panel/map-images"
for f in map-images/*.jpg map-images/*.png map-images/*.webp; do
    [ -f "$f" ] && cp "$f" "$COMPOSE_DIR/panel/map-images/"
done

docker build -t cs2_server_panel .
docker compose \
    -f "$COMPOSE_DIR/docker-compose.yml" \
    up -d \
    cs2_panel