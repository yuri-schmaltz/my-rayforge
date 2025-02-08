#!/bin/sh

set -e

# Make sure script is started from repo root.
if [ "$0" != 'flatpak/build-flatpak.sh' ]; then
    echo -e '\033[31m(ERROR)\033[0m: Script called from wrong dir. Please, read: https://developer.gimp.org/core/setup/build/linux/'
    exit 1
fi

flatpak run org.flatpak.Builder \
    --force-clean --sandbox --user --install --ccache \
    --install-deps-from=flathub \
    --mirror-screenshots-url=https://dl.flathub.org/media/ \
    --repo=repo builddir com.barebaric.rayforge.yml
