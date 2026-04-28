"""MASAV file format generator — matches the Israeli bank fixed-width spec
that the legacy Access app (`Form_msv: prep` in mtt2003local.mdb) produces.

Per-institution structure:

  K-record (header)        institution + charge date + today's date + name
  1-records (details)      one per (asmachta, bank, branch, account, name) group;
                           amounts SUMMED within the group
  5-record (trailer)       institution + total amount + group count

Then 128 "9" characters as terminator.

Hebrew names are encoded via `oldheb()` — a remap that mirrors the legacy
`oldheb` VBA function in module Hork: cp1255 codes >224 shift down by 160
(Hebrew range -> printable Latin), aleph (224) -> "&", and the result is
reversed so RTL text reads LTR on the byte stream. Verified to produce
identical bytes to the bank-accepted file from 2026-04-27.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal
from typing import Iterable


def oldheb(s: str | None) -> str:
    """Convert Hebrew text to MASAV-compatible old-Hebrew encoding (reversed).

    Mirror of the legacy VBA `oldheb()`:
        n = Asc(c)              ' Windows-1255 byte
        If n > 224 Then c = Chr(n - 160)
        ElseIf n = 224 Then c = "&"
        u = c & u               ' prepend (reverse string)
    """
    if not s:
        return ''
    out = []
    for ch in s:
        try:
            b = ch.encode('cp1255')[0]
        except (UnicodeEncodeError, IndexError):
            b = ord(ch) if ord(ch) < 256 else 32
        if b > 224:
            ch = chr(b - 160)
        elif b == 224:
            ch = '&'
        out.append(ch)
    return ''.join(reversed(out))


def _rjust_truncate(s: str, n: int) -> str:
    """Right-justify in a fixed-width field — matches the VBA
    `Format(left(s, n), String(n, "@"))` (the "@" placeholder fills from
    the right, putting Hebrew names visually correct after `oldheb` reversal).
    """
    s = s or ''
    return s[:n].rjust(n, ' ')


def _zfill(n, width: int) -> str:
    if n is None or n == '':
        n = 0
    try:
        return str(int(n)).zfill(width)
    except (ValueError, TypeError):
        return str(n)[:width].rjust(width, '0')


def write_masav_file(path: str, *, charge_date, today,
                     loans: Iterable, mosadot: dict, members: dict) -> tuple[int, int]:
    """Write a MASAV fixed-width file to `path`.

    Args:
        path: output file path
        charge_date: date the bank should debit on (used in K and 5 records as ddmmyy)
        today: file-creation date (used in K record as ddmmyy)
        loans: GemachLoan rows to charge (already filtered by date/day)
        mosadot: {institution_id: GemachInstitution}
        members:  {member_id: GemachMember}

    Returns:
        (group_count, total_agorot)  -- summary numbers for the metadata sidecar.
    """
    # Bucket loans by institution.
    by_mosad: dict[int, list] = defaultdict(list)
    for l in loans:
        by_mosad[l.institution_id].append(l)

    hdate = charge_date.strftime('%d%m%y')
    tdate = today.strftime('%d%m%y')

    grand_count = 0
    grand_total = 0

    with open(path, 'w', encoding='cp862', errors='replace', newline='\r\n') as f:
        for mosad_id, mloans in by_mosad.items():
            mosad = mosadot.get(mosad_id)
            if mosad is None:
                continue

            nmosad8 = _zfill(mosad.code, 8)
            shem    = _rjust_truncate(oldheb(mosad.name), 15)

            # K-record
            f.write(
                'K' + nmosad8 + '00' + hdate + '00010' + tdate
                + ('0' * 11) + (' ' * 15) + shem + (' ' * 56) + 'KOT' + '\n'
            )

            # Group: (asmachta, bank, snif, heshbon, name) — same as Access's
            # `GROUP BY asmachta, bank, snif, heshbon, code_mosad, shem_mosad, name, num_mosad`.
            # Sum amounts per group.
            groups: 'OrderedDict[tuple, dict]' = OrderedDict()
            for l in mloans:
                m    = members.get(l.member_id)
                full = ((m.last_name or '') + ' ' + (m.first_name or '')).strip() if m else ''
                name = oldheb(full)
                key = (
                    l.asmachta or 0,
                    l.bank_code or 0,
                    l.branch_code or 0,
                    str(l.account_number or '0'),
                    name,
                )
                if key not in groups:
                    groups[key] = {
                        'amount':   Decimal('0'),
                        'count':    0,
                        'first':    l,
                        'name':     name,
                        'asmachta': l.asmachta,
                    }
                groups[key]['amount'] += Decimal(str(l.amount or 0))
                groups[key]['count']  += 1

            section_count = 0
            section_total = 0
            for (asm, bank_n, snif_n, hesh_s, _name), g in groups.items():
                bank    = _zfill(bank_n,  10)
                snif    = _zfill(snif_n,   3)
                heshbon = _zfill(hesh_s,  13)
                agorot  = int(g['amount'] * 100)
                schum   = str(agorot).zfill(13)
                # When the loan-table asmachta is null/0, fall back to the first
                # loan's gmach_num_hork — matches what the bank-accepted file
                # showed for Hebrew sandbox data.
                disp_asmachta = g['asmachta'] or g['first'].gmach_num_hork or 0
                asmach  = _zfill(disp_asmachta, 20)
                name    = _rjust_truncate(g['name'], 16)

                f.write(
                    '1' + nmosad8 + bank + snif + heshbon
                    + ('0' * 10) + name + schum + asmach
                    + ('0' * 11) + '504' + ('0' * 18) + '  ' + '\n'
                )
                section_total += agorot
                section_count += 1

            # 5-record
            f.write(
                '5' + nmosad8 + '00' + hdate + '0001'
                + str(section_total).zfill(30) + str(section_count).zfill(14)
                + (' ' * 63) + '\n'
            )

            grand_count += section_count
            grand_total += section_total

        # File terminator
        f.write('9' * 128 + '\n')

    return grand_count, grand_total
