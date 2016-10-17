"""tsim.py: tossim simulation helper."""
import os
import re
import TOSSIM

__author__ = "Raido Pahtma"
__license__ = "MIT"


class DummyTossimLive():

    def process(self):
        pass

    def initialize(self):
        pass

    def checkThrottle(self):
        pass


def find_2nd(str1, substr1):
    return str1.find(substr1, str1.find(substr1)+1)


def format_log_line(line):
    l = line.find(" E|")
    if l >= 0:
        return '\033[91m' + line.rstrip() + '\033[0m'
    l = line.find(" W|")
    if l >= 0:
        return '\033[93m' + line.rstrip() + '\033[0m'
    return line.rstrip()


class StartStopEvent(object):

    def __init__(self, node, is_start, event_time):
        self.node = node
        self.is_start = is_start
        self.event_time = event_time

    def __cmp__(self, other):
        return self.event_time - other.event_time

    def __repr__(self):
        if self.is_start:
            return "<%04X boot %u>" % (self.node, self.event_time)
        else:
            return "<%04X stop %u>" % (self.node, self.event_time)


class TossimSimulation(object):

    def __init__(self, motexml, dt_types, log_dir, log_conf, boot_conf, link_conf, sf_port=9001):
        self.tossim = TOSSIM.Tossim([])
        self.radio = self.tossim.radio()
        self.nodes = set()
        self._sf_port = sf_port
        self._log_dir = log_dir
        self._log_conf = log_conf
        self._boot_conf = boot_conf
        self._link_conf = link_conf
        self._log_files = {}
        self._motexml = motexml

        if not os.path.exists(self._log_dir):
            os.makedirs(self._log_dir)

        self._pretty_stdout = None

        if self._motexml is not None:
            self._trans = self._motexml.MoteXMLTranslator(dt_types)
        else:
            self._trans = None

        self._xmltag = "_XML_"

        self._throttle = DummyTossimLive()
        self._throttle_start = 0
        self._sf = DummyTossimLive()

        self._process_stdout = False
        self._stdout = None
        self._end_time = None

        self._events = []
        self._simulation_script = None

    def configure_logs(self):
        with open(self._log_conf) as f:
            lines = f.readlines()
            for line in lines:
                line = line.lstrip().rstrip()
                if line.startswith("#") is False and len(line) > 0:
                    try:
                        file, channel = line.split(",")
                        file = file.lstrip().rstrip()
                        channel = channel.lstrip().rstrip()
                        if file == "stdout.txt" or file == "stdout":
                            if self._stdout is None:
                                self._stdout = open(os.path.join(self._log_dir, "stdout.txt"), "w")
                            self.tossim.addChannel(channel, self._stdout)
                        else:
                            if file not in self._log_files:
                                self._log_files[file] = open(os.path.join(self._log_dir, file), "w")
                                print("Opened logfile %s" % (file))

                            self.tossim.addChannel(channel, self._log_files[file])
                        print("Added channel %s to %s", channel, file)

                    except ValueError:
                        print("Problem with line %s", line)

    def boot_nodes(self):
        with open(self._boot_conf) as f:
            lines = f.readlines()
            for line in lines:
                line = line.lstrip().rstrip()
                if line.startswith("#") is False and len(line) > 0:
                    try:
                        splits = line.split(",")
                        node = int(splits.pop(0), 16)
                        self.nodes.add(node)
                        boot = None
                        current_is_start = False
                        for evt in splits:
                            if boot is None:
                                boot = int(evt)
                            else:
                                try:
                                    sse = StartStopEvent(node, current_is_start, int(evt)*self.tossim.ticksPerSecond()/1000)
                                    self._events.append(sse)
                                    # We use a dummy packet delivery to address 0 to get a break in the simulation at
                                    # the right time, since there is no turnOffAt command in TOSSIM. First boot events
                                    # are scheduled with bootAtTime, the rest are handled during simulation
                                    pkt = self.tossim.newPacket()
                                    pkt.setData("")
                                    pkt.setType(0)
                                    pkt.setDestination(0)
                                    pkt.deliver(0, sse.event_time)
                                except ValueError:
                                    raise ValueError("Problem parsing node %04X start-stop event %s" % (evt))

                                current_is_start = not current_is_start

                        if boot is not None:
                            m = self.tossim.getNode(node)
                            m.bootAtTime(boot * self.tossim.ticksPerSecond() / 1000)

                    except ValueError:
                        raise ValueError("Problem with line %s", line)

        self._events = sorted(self._events)

    def add_links(self, noise_lines):
        with open(self._link_conf) as f:
            lines = f.readlines()
            nodes = []
            for line in lines:
                line = line.lstrip().rstrip()
                if line.startswith("#") is False and len(line) > 0:
                    if line.startswith("----"):
                        if len(nodes) > 0:
                            raise ValueError("Only one header line allowed")

                        line = line.lstrip("----,")
                        text_nodes = line.split(",")
                        for n in text_nodes:
                            nodes.append(int(n, 16))
                    elif len(nodes) > 0:
                        values = line.split(",")
                        node_id = int(values.pop(0), 16)
                        if node_id in nodes:
                            if len(values) == len(nodes):
                                for i in xrange(len(nodes)):
                                    try:
                                        v = int(values[i])
                                        self.radio.add(node_id, nodes[i], v)
                                        print("Adding link %04X->%04X %i", node_id, nodes[i], v)
                                    except ValueError:
                                        pass

            for line in noise_lines:
                str1 = line.strip()
                if str1:
                    val = int(str1)
                    for node in nodes:
                        self.tossim.getNode(node).addNoiseTraceReading(val)

            for node in nodes:
                self.tossim.getNode(node).createNoiseModel()

    def find_hex_xml_data(self, line):
        xml_line = line.find(self._xmltag)
        if xml_line >= 0:
            data = re.sub(r'\s', '', line[xml_line + len(self._xmltag):])
            xdata = self._trans.translate_to_xml(data.decode("hex"))
            xml_data = self._motexml.xml_to_string(xdata)
            fle = xml_data.find("\n") + 1  # strip line 1
            fle = fle + xml_data[fle:].find("\n") + 1  # strip line 2
            lle = fle + xml_data[fle:-1].rfind("\n") + 1  # strip last line
            if fle == lle:
                return None
            return xml_data[fle:lle]
        return None

    def set_live(self, throttle_start):
        self._sf = TOSSIM.SerialForwarder(self._sf_port)
        self._throttle_start = throttle_start
        self._throttle = None

    def run(self):
        self._sf.process()

        if self._stdout is None:
            self._process_stdout = False

        if self._process_stdout and self._pretty_stdout is not None:
            pretty_stdout = open(os.path.join(self._log_dir, self._pretty_stdout), "w")
        else:
            pretty_stdout = None

        stdout_offset = 0  # Remember where we are in the log file
        interrupted = False
        while not interrupted:
            try:
                if self._throttle is None:
                    if self.tossim.time() > self._throttle_start * self.tossim.ticksPerSecond():
                        print("Initializing throttle")
                        self._throttle = TOSSIM.Throttle(self.tossim, 10)
                        self._throttle.initialize()
                else:
                    self._throttle.checkThrottle()

                self.tossim.runNextEvent()

                if self._simulation_script is not None:
                    self._simulation_script.tick()
                self._sf.process()

                if len(self._events) > 0:
                    if self.tossim.time() >= self._events[0].event_time:
                        evt = self._events.pop(0)
                        if evt.is_start:
                            self.tossim.getNode(evt.node).turnOn()
                            print("turning ON node %04X at %u(requested %u, offset %u)" %
                                  (evt.node, self.tossim.time(), evt.event_time,
                                   (self.tossim.time() - evt.event_time) / (self.tossim.ticksPerSecond() / 1000.0)))
                        else:
                            print("turning OFF node %04X at %u(requested %u, offset %u)" %
                                  (evt.node, self.tossim.time(), evt.event_time,
                                   (self.tossim.time() - evt.event_time) / (self.tossim.ticksPerSecond() / 1000.0)))
                            self.tossim.getNode(evt.node).turnOff()

                if self._process_stdout:
                    runlog_in = open(os.path.join(self._log_dir, "stdout.txt"), "r")
                    runlog_in.seek(stdout_offset, 0)
                    for line in runlog_in:
                        pretty = format_log_line(line)
                        print(pretty)
                        if pretty_stdout is not None:
                            pretty_stdout.write(pretty)
                            pretty_stdout.write("\n")

                        if self._motexml is not None:
                            xdata = self.find_hex_xml_data(line)
                            if xdata is not None:
                                line_head = line[:find_2nd(line, "|")+1]
                                for line in xdata.splitlines():
                                    pretty = line_head + '\033[94m' + line + '\033[0m'
                                    print(pretty)
                                    if pretty_stdout is not None:
                                        pretty_stdout.write(pretty)
                                        pretty_stdout.write("\n")

                    stdout_offset = runlog_in.tell()
                    runlog_in.close()

                if self._over():
                    break

            except KeyboardInterrupt:
                interrupted = True

        if pretty_stdout is not None:
            pretty_stdout.close()

        for f in self._log_files.values():
            f.close()

        if self._stdout is not None:
            self._stdout.close()

        if interrupted:
            print("Simulation interrupted")
        else:
            print("Simulation over")

    def set_pretty_stdout(self, pretty_stdout):
        self._pretty_stdout = pretty_stdout

    def set_process_stdout(self):
        self._process_stdout = True

    def set_end_time(self, end_time):
        self._end_time = end_time
        # We use a dummy packet delivery to address 0 to get a break in the simulation at the right time
        pkt = self.tossim.newPacket()
        pkt.setData("")
        pkt.setType(0)
        pkt.setDestination(0)
        pkt.deliver(0, end_time*self.tossim.ticksPerSecond())

    def _over(self):
        if self._end_time is not None:
            if self.tossim.time() >= self._end_time * self.tossim.ticksPerSecond():
                return True
        return False

    def set_script_module(self, script_module):
        self._simulation_script = script_module.get_simulation_script(self)


def main():
    import argparse
    import importlib
    import sys

    parser = argparse.ArgumentParser(description="simulation arguments",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--process-stdout", default=False, action="store_true",
                        help="Process stdout for color and stuff")
    parser.add_argument("--pretty-stdout", default="pretty_stdout.txt",
                        help="Save processed stdout to file, requires --process-stdout")

    parser.add_argument("--motexml", default=False, action="store_true")
    parser.add_argument("--dt-types", default="dt_types.txt")

    parser.add_argument("--log-conf", default="tsim-logs.txt")
    parser.add_argument("--boot-conf", default="tsim-boots.txt")
    parser.add_argument("--link-conf", default="tsim-links.csv")

    parser.add_argument("--noise-model", default="no-noise.txt")

    parser.add_argument("--log-dir", default="~/tsim_log")

    parser.add_argument("--live", default=False, action="store_true")
    parser.add_argument("--port", default=9001, type=int, help="sim-sf SerialForwarder port.")
    parser.add_argument("--throttle-start", default=0, type=int,
                        help="Start throttling the simulation after this amount of seconds have passed.")

    parser.add_argument("--end-time", default=None, type=int,
                        help="End time of simulation in seconds, default is to run until interrupted.")

    parser.add_argument("--simulation-script", default=None, help="Path to a ")

    args = parser.parse_args()

    if args.motexml:
        import motexml.motexml as motexml
    else:
        motexml = None

    ts = TossimSimulation(motexml, args.dt_types, args.log_dir, args.log_conf, args.boot_conf, args.link_conf, sf_port=args.port)

    ts.boot_nodes()

    if args.live:
        ts.set_live(args.throttle_start)

    if args.process_stdout:
        ts.set_process_stdout()
        if args.pretty_stdout is not None:
            ts.set_pretty_stdout(args.pretty_stdout)

    if args.end_time is not None:
        ts.set_end_time(args.end_time)

    if args.simulation_script is not None:
        try:
            path = os.path.dirname(os.path.abspath(args.simulation_script))
            filename = os.path.basename(args.simulation_script)
            module_name = filename.rstrip(".py")
            sys.path.insert(0, path)
            script_module = importlib.import_module(module_name)
            print("Imported simulation script from module %s in %s" % (module_name, path))
            ts.set_script_module(script_module)
        except ImportError:
            print("Unable to import simulation script from module %s" % (args.simulation_script))
            sys.exit(1)

    ts.configure_logs()

    with open(args.noise_model, "r") as noise:
        ts.add_links(noise.readlines())

    ts.run()

    sys.exit(0)

if __name__ == '__main__':
    main()
