"""CLI for reproducible offline experiments without the dashboard."""
import argparse
import json
import logging
from pathlib import Path

from pvforecast.data import read_file, prepare, content_hash
from pvforecast.forecast import forecast, forecast_table
from pvforecast.model import Config, train, unpack, save_bundle
from pvforecast.storage import persist_dataset


def main():
    parser = argparse.ArgumentParser(description="DTINS PV · Historical Replay")
    parser.add_argument("command", choices=["audit", "train", "forecast"])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--origin", help="ISO 8601 timestamp with timezone")
    parser.add_argument("--output", type=Path, default=Path("data/exports"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        raw = args.data.read_bytes()
        mapping = config["data"]
        dataset = prepare(read_file(raw, args.data.name, mapping.get("sheet", 0)),
                          mapping["timestamp_column"], mapping["power_column"], mapping["timezone"],
                          dayfirst=mapping.get("dayfirst", False), source_file=args.data.name,
                          source_hash=content_hash(raw))
        persist_dataset(raw, args.data.name, dataset)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "quality.json").write_text(json.dumps(dataset.report, indent=2), encoding="utf-8")
        dataset.clean.to_csv(args.output / "clean.csv", index=False)
        if args.command == "train":
            candidates = [Config(**item) for item in config["candidates"]]
            bundle = train(dataset.clean, config["boundaries"], candidates, dataset.report,
                           lambda t, total, e, loss: logging.info("Trial %s/%s epoch %s val_loss %.6f", t, total, e, loss))
            print(save_bundle(bundle))
        elif args.command == "forecast":
            if args.model is None or not args.origin:
                parser.error("forecast memerlukan --model dan --origin")
            result = forecast(dataset, unpack(args.model.read_bytes()), args.origin)
            (args.output / "forecast.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
            forecast_table(result).to_csv(args.output / "forecast.csv", index=False)
            print(args.output / "forecast.json")
        else:
            print(json.dumps(dataset.report, indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
