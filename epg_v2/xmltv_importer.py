import gzip
import xml.etree.ElementTree as ET


class XMLTVImporter:

    def __init__(self, datei):
        self.datei = datei
        self.root = None

    def laden(self):

        if self.datei.endswith(".gz"):

            with gzip.open(self.datei, "rb") as f:
                self.root = ET.parse(f).getroot()

        else:

            self.root = ET.parse(self.datei).getroot()

        return self.root

    def channels(self):

        return self.root.findall("channel")

    def programmes(self):

        return self.root.findall("programme")