import argparse
import json

from hlbot.backtest.demo_workflow import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m hlbot")
    subcommands = parser.add_subparsers(dest="command", required=True)
    backtest = subcommands.add_parser("backtest", help="run illustrative offline WS replay")
    backtest.add_argument("--config", default="configs/demo_backtest.json")
    backtest.add_argument("--data", default="data/sample")
    backtest.add_argument("--output", default="reports/demo_backtest.json")
    args = parser.parse_args()

    if args.command == "backtest":
        report = run_backtest(args.config, args.data, args.output)
        print(json.dumps({
            "market": report["market"], "input": report["input"],
            "replay": report["replay"], "performance": report["performance"],
            "report_path": args.output,
        }, indent=2))


if __name__ == "__main__":
    main()
