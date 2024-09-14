import json
from pathlib import Path
from typing import Any


def log_to_json(log_file: Path, remove_log: bool = False) -> list[dict[str, int | str]]:
    """Converts a log file to a json file
        過去大会のログファイルをjson(list[dict[str, str]])に変換する


    Args:
        log_file (Path): Log file path
        remove_log (bool, optional): Whether to remove the log file. Defaults to False.

    Returns:
        list[dict[str, int | str]]: List of dict
    """
    with open(log_file, mode="r") as f:
        log_lines = [line.rstrip("\r\n") for line in f.readlines()]
    output_dictlist = []
    for row in log_lines[5:-8]:
        fields = row.split(",")
        if len(fields) == 6:
            try:
                output_dictlist.append(
                    {
                        "agent": int(fields[4]),
                        "day": int(fields[0]),
                        "idx": int(fields[2]),
                        "text": fields[5],
                        "turn": int(fields[3]),
                    }
                )
            except:
                pass

    json_file = log_file.with_suffix(".json")
    with open(json_file, mode="w") as f:
        json.dump(output_dictlist, f, indent=4, ensure_ascii=False)
    if remove_log:
        log_file.unlink()
    return output_dictlist


if __name__ == "__main__":
    log_filelist: list[Path] = Path("data").glob("*.log")
    for log_file in log_filelist:
        _ = log_to_json(log_file)
