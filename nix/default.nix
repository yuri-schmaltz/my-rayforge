{
  description = "Rayforge fork - laser cutter/engraver controller";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        rayforge-fork = pkgs.stdenv.mkDerivation rec {
          pname = "rayforge-fork";
          version = "1.9.0+resilience.5";

          src = pkgs.fetchurl {
            url = "https://github.com/yuri-schmaltz/rayforge/archive/refs/tags/${version}.tar.gz";
            sha256 = "REPLACE_WITH_SHA256";
          };

          nativeBuildInputs = with pkgs; [
            pixi
            python3
            python3Packages.build
            python3Packages.installer
            python3Packages.wheel
          ];

          buildInputs = with pkgs; [
            gtk4
            libadwaita
            python3Packages.pygobject3
            python3Packages.pycairo
            librsvg
            poppler
            libusb
            cython
          ];

          buildPhase = ''
            pixi install --frozen
            pixi run -e build python -m build --wheel
            pixi run -e build compile-translations
          '';

          installPhase = ''
            PIXI_PYTHON=$(pixi run -e build python -c "import sys; print(sys.executable)")
            $PIXI_PYTHON -m installer --destdir=$out dist/rayforge*.whl
            install -Dm644 resources/rayforge.desktop \
              $out/share/applications/rayforge.desktop
            install -Dm644 resources/icons/rayforge.svg \
              $out/share/icons/hicolor/scalable/apps/rayforge.svg
            install -Dm644 LICENSE $out/share/licenses/rayforge-fork/LICENSE
          '';

          meta = with pkgs.lib; {
            description = "Laser cutter/engraver controller (community fork with resilience patches)";
            homepage = "https://github.com/yuri-schmaltz/rayforge";
            license = licenses.mit;
            platforms = platforms.linux;
          };
        };
      in
      {
        packages.default = rayforge-fork;
      });
}
