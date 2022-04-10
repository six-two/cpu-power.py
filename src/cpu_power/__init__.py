#!/usr/bin/env python3
import argparse
import sys
import os
import time
import traceback
from typing import Optional
import re

FREQ_REGEX = re.compile(r"^cpu MHz\s*:\s*(\d+)\.")
# cpu<N>
REGEX_VALID_CORE_NAME = re.compile(r"^cpu\d+$")
REGEX_VALID_CORE_NAME_EXCLUDE_CPU0 = re.compile(r"^cpu[1-9]\d*$")

DEBUG = False


def read_file(path: str) -> str:
    with open(path, "r") as f:
        contents = f.read()
    
    if DEBUG:
        print(f"[DEBUG] File read {repr(contents)} from {path}")
    return contents


def write_file(path: str, contents: str) -> None:
    if DEBUG:
        print(f"[DEBUG] File write '{contents}' -> {path}")

    with open(path, "w") as f:
        f.write(str(contents))

def write_bool_to_file(path: str, value: bool) -> None:
    write_file(path, "1" if value else "0")


def parse_bool(boolean_as_text: str) -> bool:
    value = boolean_as_text.strip()
    if value in ["1", "on"]:
        return True
    elif value in ["0", "off"]:
        return False
    else:
        raise Exception(f"Can not parse as boolean: '{boolean_as_text}'")


class CpuManager:
    def __init__(self):
        raise Exception("You do not need to instanciate this class, it has only static functions")

    @staticmethod
    def is_boost_enabled() -> bool:
        text = read_file("/sys/devices/system/cpu/cpufreq/boost")
        return parse_bool(text)

    @staticmethod
    def set_boost(enabled: bool) -> None:
        write_bool_to_file("/sys/devices/system/cpu/cpufreq/boost", enabled)

    @staticmethod
    def is_smt_enabled() -> bool:
        text = read_file("/sys/devices/system/cpu/smt/active")
        return parse_bool(text)

    @staticmethod
    def set_smt(enabled: bool) -> None:
        value = "on" if enabled else "off"
        write_file("/sys/devices/system/cpu/smt/control", value)

    @staticmethod
    def get_freq_span() -> tuple[int, int]:
        """
        @TODO
        Sadly, this approach requires root permissions, maybe revert to parsing /proc/cpuinfo
        """
        min_freq = 1000000
        max_freq = 0
        for core_num, is_enabled in enumerate(CpuManager.get_core_status()):
            if is_enabled:
                freq_path = f"/sys/devices/system/cpu/cpu{core_num}/cpufreq/cpuinfo_cur_freq"
                text = read_file(freq_path)
                freq = int(text) / 1000
                min_freq = min(min_freq, freq)
                max_freq = max(max_freq, freq)

        return (min_freq, max_freq)

    @staticmethod
    def get_available_freq_list() -> list[int]:
        freq_list = read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies").split()
        # convert strings to ints. Convert hertz into kilohertz
        freq_list = [int(x) / 1000 for x in freq_list if x]
        return sorted(freq_list)

    @staticmethod
    def set_min_freq(freq_in_mhz: int):
        for core_num, is_enabled in enumerate(CpuManager.get_core_status()):
            if is_enabled:
                freq_path = f"/sys/devices/system/cpu/cpu{core_num}/cpufreq/scaling_min_freq"
                write_file(freq_path, str(freq_in_mhz * 1000))

    @staticmethod
    def set_max_freq(freq_in_mhz: int):
        for core_num, is_enabled in enumerate(CpuManager.get_core_status()):
            if is_enabled:
                freq_path = f"/sys/devices/system/cpu/cpu{core_num}/cpufreq/scaling_max_freq"
                write_file(freq_path, str(freq_in_mhz * 1000))

    @staticmethod
    def get_core_status() -> list[bool]:
        result = []
        try:
            # for some reason cpu0 did not have a online attribute
            # TODO: maybe investigate
            # For low, let's just assume it is always online
            result.append(True)

            for index in range(1, 100000):
                # If it has more that that many cores, there is probably some error or something
                text = read_file(f"/sys/devices/system/cpu/cpu{index}/online")
                is_online = parse_bool(text)
                result.append(is_online)
            raise Exception("I am pertty sure you do not have that many cores ;)")
        except FileNotFoundError:
            # no more CPUs exist
            pass
        return result

    @staticmethod
    def set_core_count(target: int) -> None:
        if target < 1:
            raise Exception(f"Invalid CPU core target: {target}. Needs to be 1 or higher")

        # CPU indices start at 0, but CPU0 can/should probably not be disabled :)
        for index in range(1, 100000):
            # If it has more that that many cores, there is probably some error or something
            try:
                value = "1" if index < target else "0"
                write_file(f"/sys/devices/system/cpu/cpu{index}/online", value)
            except FileNotFoundError:
                if index < target:
                    raise Exception(f"Can't reach target of {target} cores, because your system only has {index} virtual cores")
                return
        raise Exception("I am pertty sure you do not have that many cores ;)")

    @staticmethod
    def get_cpu_core_dirs(exclude_cpu0: bool = False) -> list[str]:
        """
        Returns a list of directories matching /sys/devices/system/cpu/cpu<N>, where <N> is a number
        """
        root = "/sys/devices/system/cpu/"
        regex = REGEX_VALID_CORE_NAME_EXCLUDE_CPU0 if exclude_cpu0 else REGEX_VALID_CORE_NAME
        return [os.path.join(root, x) for x in os.listdir(root) if regex.match(x)]




class ErrorHandler:
    def __init__(self, show_traceback) -> None:
        self.has_error = False
        self.show_traceback = show_traceback

    def try_fn(self, function, error_message: Optional[str], success_message: Optional[str] = None):
        try:
            result = function()
            if success_message:
                print("[OK]", success_message)
            return result
        except Exception:
            self.has_error = True
            if error_message:
                print("[ERROR]", error_message)
            if self.show_traceback:
                traceback.print_exc()

    def get_exit_code(self):
        return 1 if self.has_error else 0


def subcommand_info(args) -> int:
    def bool_to_str(x: bool) -> str:
        return "enabled" if x else "disabled"

    def show_boost():
        is_boost_on = CpuManager.is_boost_enabled()
        pretty_boost = bool_to_str(is_boost_on)
        print(f"Boost          : {pretty_boost}")

    def show_smt():
        is_smt_on = CpuManager.is_smt_enabled()
        pretty_smt = bool_to_str(is_smt_on)
        print(f"SMT            : {pretty_smt}")

    def show_core_count():
        core_status_list = CpuManager.get_core_status()
        online_count = len([x for x in core_status_list if x])
        total_count = len(core_status_list)
        print(f"Cores          : {online_count} / {total_count}")

    def show_freq():
        freq_min, freq_max = CpuManager.get_freq_span()
        pretty_freq = f"{int(freq_min)}"
        if freq_min != freq_max:
            pretty_freq += f" - {int(freq_max)}"
        print(f"Current freq   : {pretty_freq} MHz")

    def show_available_freq():
        freq_list = CpuManager.get_available_freq_list()
        pretty_freq = ", ".join([f"{int(x)} MHz" for x in freq_list])
        print(f"Available freq : {pretty_freq}")

    error_handler = ErrorHandler(args.verbose)
    error_handler.try_fn(show_core_count, "Failed to get CPU core count")
    error_handler.try_fn(show_smt, "Failed to get SMT status")
    error_handler.try_fn(show_boost, "Failed to get CPU boost")
    error_handler.try_fn(show_freq, "Failed to get CPU frequency")
    error_handler.try_fn(show_available_freq, "Failed to get available CPU frequencies")
    return error_handler.get_exit_code()


def subcommand_set(args) -> int:
    if os.geteuid() != 0:
        print("You need to run this script as root")
        return 1
    
    error_handler = ErrorHandler(args.verbose)

    if args.cores != None:
        error_handler.try_fn(lambda: CpuManager.set_smt(True), "Failed enabling SMT")
        error_handler.try_fn(lambda: CpuManager.set_core_count(args.cores), "Failed to enable target number of cores")
    elif args.smt != None:
        error_handler.try_fn(lambda: CpuManager.set_smt(args.smt), "Failed updating SMT")

    if args.boost != None:
        error_handler.try_fn(lambda: CpuManager.set_boost(args.boost), "Failed updating boost")
    
    if args.min_freq:
        min_freq = int(args.min_freq * 1000)
        error_handler.try_fn(lambda: CpuManager.set_min_freq(min_freq), "Failed setting minimum frequency")

    if args.max_freq:
        max_freq = int(args.max_freq * 1000)
        error_handler.try_fn(lambda: CpuManager.set_max_freq(max_freq), "Failed setting maximum frequency")

    if args.min_freq or args.max_freq:
        # Wait a bit to give the settings time to update
        time.sleep(0.1)

    # Show the new values, so that I can see if the opperation succeeded
    if subcommand_info(args) != 0:
        error_handler.has_error = True
    return error_handler.get_exit_code()


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true", help="show verbose error messages")
    subparsers = ap.add_subparsers(dest="cmd")

    def add_bool_flag(parser, short: str, long: str, help: str) -> None:
        # This will add a --feature and a --no-feature flag

        # bot flags    -> show error message
        feature_parser = parser.add_mutually_exclusive_group(required=False)
        # --feature    -> True
        feature_parser.add_argument(f"-{short.lower()}", f"--{long}", dest=long, action='store_true', help=f"Enable {help}")
        # --no-feature -> False
        feature_parser.add_argument(f"-{short.upper()}", f"--no-{long}", dest=long, action='store_false', help=f"Disable {help}")
        # No flags     -> None
        parser.set_defaults(**{long: None})

    def add_subparser(name: str, description: str):
        return subparsers.add_parser(name, description=description, help=description)
    
    set_parser = add_subparser("set", "[requires root] manually set some CPU performance parameters")
    add_bool_flag(set_parser, "s", "smt", "Simultaneous Multi-Threading")
    add_bool_flag(set_parser, "b", "boost", "CPU performance boost")
    set_parser.add_argument("-c", "--cores", type=int, help="Set the number of cores manually. Will ignore any additional --smt or --no-smt flags")
    set_parser.add_argument("-d", "--min-freq", type=float, help="set the CPU minimum frequency. The value is interpreted as a frequency in GHz")
    set_parser.add_argument("-u", "--max-freq", type=float, help="set the CPU minimum frequency. The value is interpreted as a frequency in GHz")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    if args.verbose:
        DEBUG = True

    cmd = args.cmd
    code = 1
    if cmd == "set":
        code = subcommand_set(args)
    else:
        code = subcommand_info(args)

    return code


if __name__ == "__main__":
    sys.exit(main())
