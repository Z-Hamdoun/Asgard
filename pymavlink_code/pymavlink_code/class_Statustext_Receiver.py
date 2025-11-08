import time

class PendingText(object):
    """Permet la réception d'un seul statustext"""
    def __init__(self):
        self.expected_count = None
        self.severity = None
        self.chunks = {}
        self.start_time = time.time()
        self.last_chunk_time = time.time()

    def add_chunk(self, m): # m is a statustext message
        self.severity = m.severity
        self.last_chunk_time = time.time()
        if hasattr(m, 'chunk_seq'):
            # mavlink extensions are present.
            chunk_seq = m.chunk_seq
            mid = m.id
        else:
            # Note that m.id may still exist!  It will
            # contain the value 253, STATUSTEXT's mavlink
            # message id.  Thus our reliance on the
            # presence of chunk_seq.
            chunk_seq = 0
            mid = 0
        self.chunks[chunk_seq] = m.text

        if len(m.text) != 50 or mid == 0:
            self.expected_count = chunk_seq + 1

    def complete(self):
        return (self.expected_count is not None and
                self.expected_count == len(self.chunks))

    def accumulated_statustext(self):
        next_expected_chunk = 0
        out = ""
        for chunk_seq in sorted(self.chunks.keys()):
            if chunk_seq != next_expected_chunk:
                out += " ... "
                next_expected_chunk = chunk_seq
            if isinstance(self.chunks[chunk_seq], str):
                out += self.chunks[chunk_seq]
            else:
                out += self.chunks[chunk_seq].decode(errors="ignore")
            next_expected_chunk += 1

        return out

class Statustext_Receiver:
    """Permet de gérer la réception des statustext découpés en chunk"""
    def __init__(self):
        self._statustexts_by_sysidcompid = {}
        self._last_statustext = {}
    
    def last_statustext_from_sysidcompid(self, key):
        """Renvoie le dernier statustext complet reçu de (sysid, compid). None si pas de dernier message."""
        return self._last_statustext.get(key, None)
    
    def _add(self, m):
        """Ajoute un STATUSTEXT à la réception"""
        key = (m.get_srcSystem(), m.get_srcComponent())
        if key not in self._statustexts_by_sysidcompid:
            self._statustexts_by_sysidcompid[key] = {}
        if hasattr(m, 'chunk_seq'):
            mid = m.id
        else:
            # m.id will have the value of 253, STATUSTEXT mavlink id
            mid = 0
        if mid not in self._statustexts_by_sysidcompid[key]:
            self._statustexts_by_sysidcompid[key][mid] = PendingText()

        pending: PendingText = self._statustexts_by_sysidcompid[key][mid]
        pending.add_chunk(m)
        if pending.complete():
            # we have all of the chunks!
            out = pending.accumulated_statustext()
            if key not in self._last_statustext or out != self._last_statustext[key].text or time.time() > self._last_statustext[key]._timestamp+2:
                m.text = out
                self._last_statustext[key] = m
                return m
            del self._statustexts_by_sysidcompid[key][mid]
        return None
