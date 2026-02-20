# comment
{
  description = "Telegram bot for betting on challonge matches";

  # Nixpkgs / NixOS version to use.
  inputs.nixpkgs.url = "nixpkgs/nixos-25.05";

  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    let
      version = "0.0.1";
      overlay = final: prev: {
        python3 = prev.python3.override {
          packageOverrides = finalPy: prevPy: {
          };
        };
        python3Packages = final.python3.pkgs;
      };
    in

    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = (nixpkgs.legacyPackages.${system}.extend overlay); in
      {

        packages = rec {
          default = challonge-bet-bot;
          challonge-bet-bot = pkgs.python3.pkgs.buildPythonApplication {
            pname = "challonge-bet-bot";
            src = pkgs.lib.cleanSource ./.;
            inherit version;
            pyproject = true;

            dependencies = with pkgs.python3Packages; [
              requests
              python-telegram-bot
              python-dotenv
              cachetools
            ] ++ python-telegram-bot.optional-dependencies.job-queue;

            build-system = with pkgs.python3Packages; [
              setuptools
            ];
          };
        };
        
        devShells = {
          default = pkgs.mkShell {
            inputsFrom = [ self.packages.${system}.default ];
            packages = with pkgs; [

              (python3.withPackages (ps: with ps; [

              ]))
            ];
          };
        };
      }
    );
}
