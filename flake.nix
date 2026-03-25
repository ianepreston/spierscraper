{
  description = "Spier & Mackay clearance scraper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: with ps; [
          httpx
          selectolax
          pydantic
          pyyaml
          diskcache
          tenacity

          # Dev dependencies
          pytest
          pytest-asyncio
          pytest-cov
          ruff
          mypy
          types-pyyaml
          respx
        ]);

        spierscraper = python.pkgs.buildPythonApplication {
          pname = "spierscraper";
          version = "0.1.0";
          format = "pyproject";

          src = ./.;

          nativeBuildInputs = with python.pkgs; [
            setuptools
          ];

          propagatedBuildInputs = with python.pkgs; [
            httpx
            selectolax
            pydantic
            pyyaml
            diskcache
            tenacity
          ];

          doCheck = false;
        };

        dockerImage = pkgs.dockerTools.buildLayeredImage {
          name = "spierscraper";
          tag = "latest";

          contents = [
            spierscraper
            pkgs.cacert
          ];

          config = {
            Entrypoint = [ "${spierscraper}/bin/spierscraper" ];
            Env = [
              "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            ];
          };
        };

      in {
        packages = {
          default = spierscraper;
          docker = dockerImage;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.ruff
          ];

          shellHook = ''
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
          '';
        };
      }
    );
}
