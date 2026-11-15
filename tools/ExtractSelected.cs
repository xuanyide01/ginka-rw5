using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;

public sealed class HxSplitMix64
{
    private ulong _state;
    public HxSplitMix64(ulong seed) { _state = seed; }
    public ulong Next()
    {
        unchecked
        {
            _state += 0x9E3779B97F4A7C15UL;
            ulong z = _state;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }
    }
}

public static class BitOps
{
    public static ulong RotL64(ulong x, int k) { return (x << k) | (x >> (64 - k)); }
}

public interface IHxRng { uint NextU32(); }

public sealed class Xoroshiro128PlusPlus : IHxRng
{
    private ulong _s0, _s1;
    public Xoroshiro128PlusPlus(ulong s0, ulong s1) { _s0 = s0; _s1 = s1; }
    public uint NextU32()
    {
        unchecked
        {
            ulong s0 = _s0, s1 = _s1;
            ulong res = BitOps.RotL64(s0 + s1, 17) + s0;
            s1 ^= s0;
            _s0 = BitOps.RotL64(s0, 49) ^ s1 ^ (s1 << 21);
            _s1 = BitOps.RotL64(s1, 28);
            return (uint)res;
        }
    }
}

public sealed class Xoroshiro128StarStar : IHxRng
{
    private ulong _s0, _s1;
    public Xoroshiro128StarStar(ulong s0, ulong s1) { _s0 = s0; _s1 = s1; }
    public uint NextU32()
    {
        unchecked
        {
            ulong s0 = _s0, s1 = _s1;
            ulong res = BitOps.RotL64(s0 * 5UL, 7) * 9UL;
            s1 ^= s0;
            _s0 = BitOps.RotL64(s0, 24) ^ s1 ^ (s1 << 16);
            _s1 = BitOps.RotL64(s1, 37);
            return (uint)res;
        }
    }
}

public enum OpCode : byte
{
    MovEdiArg, PushEbx, PopEbx, PushEcx, PopEcx,
    MovEbxEax, MovEaxEdi, MovEcxEbx, MovEaxEbx,
    AndEcx0F, ShrEbx1, ShlEax1, ShrEaxCl, ShlEaxCl,
    OrEaxEbx, NotEax, NegEax, DecEax, IncEax,
    AddEaxEbx, SubEaxEbx, ImulEaxEbx,
    AddEaxImmed, SubEaxImmed, AndEbxImmed, AndEaxImmed, XorEaxImmed, MovEaxImmed,
    MovEaxIndirect, Retn
}

public struct Insn { public OpCode Op; public uint Imm; }

public sealed class HxVmProgram
{
    private const int MaxLen = 0x80;
    private readonly uint[] _ctrlInv;
    private readonly IHxRng _rng;
    private readonly List<Insn> _code = new List<Insn>(64);
    private int _length;

    public HxVmProgram(uint seed, uint[] ctrlInv, int randomType)
    {
        _ctrlInv = ctrlInv;
        ulong initSeed = ((ulong)seed) | (((ulong)(~seed)) << 32);
        var sm = new HxSplitMix64(initSeed);
        ulong s0 = sm.Next();
        ulong s1 = sm.Next();
        _rng = (randomType == 0) ? (IHxRng)new Xoroshiro128PlusPlus(s0, s1) : new Xoroshiro128StarStar(s0, s1);
    }

    public void Clear() { _code.Clear(); _length = 0; }
    public uint GetRandom() { return _rng.NextU32(); }
    public bool EmitNop(int count) { if (_length + count > MaxLen) return false; _length += count; return true; }
    public bool Emit(OpCode op, int byteLen) { if (_length + byteLen > MaxLen) return false; _code.Add(new Insn { Op = op, Imm = 0 }); _length += byteLen; return true; }
    public bool EmitImmForPrev(uint val)
    {
        if (_length + 4 > MaxLen) return false;
        var prev = _code[_code.Count - 1];
        prev.Imm = val;
        _code[_code.Count - 1] = prev;
        _length += 4;
        return true;
    }

    public uint Execute(uint arg)
    {
        unchecked
        {
            uint eax = 0, ebx = 0, ecx = 0, edi = 0;
            uint[] stack = new uint[16];
            int sp = 0;
            int n = _code.Count;
            for (int i = 0; i < n; i++)
            {
                Insn ins = _code[i];
                switch (ins.Op)
                {
                    case OpCode.MovEdiArg: edi = arg; break;
                    case OpCode.PushEbx: stack[sp++] = ebx; break;
                    case OpCode.PopEbx: ebx = stack[--sp]; break;
                    case OpCode.PushEcx: stack[sp++] = ecx; break;
                    case OpCode.PopEcx: ecx = stack[--sp]; break;
                    case OpCode.MovEbxEax: ebx = eax; break;
                    case OpCode.MovEaxEdi: eax = edi; break;
                    case OpCode.MovEcxEbx: ecx = ebx; break;
                    case OpCode.MovEaxEbx: eax = ebx; break;
                    case OpCode.AndEcx0F: ecx &= 0x0FU; break;
                    case OpCode.ShrEbx1: ebx >>= 1; break;
                    case OpCode.ShlEax1: eax <<= 1; break;
                    case OpCode.ShrEaxCl: eax >>= (int)(ecx & 31U); break;
                    case OpCode.ShlEaxCl: eax <<= (int)(ecx & 31U); break;
                    case OpCode.OrEaxEbx: eax |= ebx; break;
                    case OpCode.NotEax: eax = ~eax; break;
                    case OpCode.NegEax: eax = (uint)(-(int)eax); break;
                    case OpCode.DecEax: eax -= 1U; break;
                    case OpCode.IncEax: eax += 1U; break;
                    case OpCode.AddEaxEbx: eax += ebx; break;
                    case OpCode.SubEaxEbx: eax -= ebx; break;
                    case OpCode.ImulEaxEbx: eax *= ebx; break;
                    case OpCode.AddEaxImmed: eax += ins.Imm; break;
                    case OpCode.SubEaxImmed: eax -= ins.Imm; break;
                    case OpCode.AndEbxImmed: ebx &= ins.Imm; break;
                    case OpCode.AndEaxImmed: eax &= ins.Imm; break;
                    case OpCode.XorEaxImmed: eax ^= ins.Imm; break;
                    case OpCode.MovEaxImmed: eax = ins.Imm; break;
                    case OpCode.MovEaxIndirect: eax = ~_ctrlInv[eax]; break;
                    case OpCode.Retn:
                        if (sp != 0) throw new InvalidOperationException("Stack not empty");
                        return eax;
                }
            }
            throw new InvalidOperationException("Missing Retn");
        }
    }
}

public sealed class HxCipherEngine
{
    public readonly uint Mask, Offset;
    public readonly ulong FilterKey;
    private readonly byte[] _prolog, _odd, _even;
    private readonly uint[] _ctrlInv;
    private readonly int _randomType;
    private readonly HxVmProgram[] _programs = new HxVmProgram[0x80];

    public HxCipherEngine(uint mask, uint offset, ulong filterKey, int randomType, byte[] prolog, byte[] odd, byte[] even, uint[] ctrlInv)
    {
        Mask = mask; Offset = offset; FilterKey = filterKey; _randomType = randomType;
        _prolog = prolog; _odd = odd; _even = even; _ctrlInv = ctrlInv;
        for (uint s = 0; s < 0x80; s++) _programs[s] = GenerateProgram(s);
    }

    private HxVmProgram GenerateProgram(uint seed)
    {
        var p = new HxVmProgram(seed, _ctrlInv, _randomType);
        for (int stage = 5; stage >= 1; stage--)
        {
            if (p.EmitNop(5) && p.Emit(OpCode.MovEdiArg, 4) && EmitBody(p, stage) && p.EmitNop(5) && p.Emit(OpCode.Retn, 1))
                return p;
            p.Clear();
        }
        throw new InvalidOperationException("Failed to emit HxVmProgram");
    }

    private bool EmitBody(HxVmProgram p, int stage)
    {
        if (stage == 1) return EmitProlog(p);
        if (!p.Emit(OpCode.PushEbx, 1)) return false;
        bool ok1 = ((p.GetRandom() & 1U) != 0) ? EmitBody(p, stage - 1) : EmitBody2(p, stage - 1);
        if (!ok1 || !p.Emit(OpCode.MovEbxEax, 2)) return false;
        bool ok2 = ((p.GetRandom() & 1U) != 0) ? EmitBody(p, stage - 1) : EmitBody2(p, stage - 1);
        return ok2 && EmitOdd(p) && p.Emit(OpCode.PopEbx, 1);
    }

    private bool EmitBody2(HxVmProgram p, int stage)
    {
        if (stage == 1) return EmitProlog(p);
        bool ok = ((p.GetRandom() & 1U) != 0) ? EmitBody(p, stage - 1) : EmitBody2(p, stage - 1);
        return ok && EmitEven(p);
    }

    private bool EmitProlog(HxVmProgram p)
    {
        switch (_prolog[p.GetRandom() % 3U])
        {
            case 2:
                if (!p.EmitNop(5) || !p.Emit(OpCode.MovEaxImmed, 2)) return false;
                uint rnd = p.GetRandom() & 0x3FFU;
                return p.EmitImmForPrev(rnd) && p.Emit(OpCode.MovEaxIndirect, 0);
            case 1: return p.Emit(OpCode.MovEaxEdi, 2);
            case 0: return p.Emit(OpCode.MovEaxImmed, 1) && p.EmitImmForPrev(p.GetRandom());
            default: return true;
        }
    }

    private bool EmitEven(HxVmProgram p)
    {
        switch (_even[p.GetRandom() & 7U])
        {
            case 0: return p.Emit(OpCode.NotEax, 2);
            case 1: return p.Emit(OpCode.DecEax, 1);
            case 2: return p.Emit(OpCode.NegEax, 2);
            case 3: return p.Emit(OpCode.IncEax, 1);
            case 4: return p.EmitNop(5) && p.Emit(OpCode.AndEaxImmed, 1) && p.EmitImmForPrev(0x3FFU) && p.Emit(OpCode.MovEaxIndirect, 3);
            case 5:
                return p.Emit(OpCode.PushEbx, 1) && p.Emit(OpCode.MovEbxEax, 2)
                    && p.Emit(OpCode.AndEbxImmed, 2) && p.EmitImmForPrev(0xAAAAAAAAU)
                    && p.Emit(OpCode.AndEaxImmed, 1) && p.EmitImmForPrev(0x55555555U)
                    && p.Emit(OpCode.ShrEbx1, 2) && p.Emit(OpCode.ShlEax1, 2)
                    && p.Emit(OpCode.OrEaxEbx, 2) && p.Emit(OpCode.PopEbx, 1);
            case 6: return p.Emit(OpCode.XorEaxImmed, 1) && p.EmitImmForPrev(p.GetRandom());
            case 7: return p.Emit(((p.GetRandom() & 1U) != 0) ? OpCode.AddEaxImmed : OpCode.SubEaxImmed, 1) && p.EmitImmForPrev(p.GetRandom());
            default: return true;
        }
    }

    private bool EmitOdd(HxVmProgram p)
    {
        switch (_odd[p.GetRandom() % 6U])
        {
            case 0: return p.Emit(OpCode.PushEcx, 1) && p.Emit(OpCode.MovEcxEbx, 2) && p.Emit(OpCode.AndEcx0F, 3) && p.Emit(OpCode.ShrEaxCl, 2) && p.Emit(OpCode.PopEcx, 1);
            case 1: return p.Emit(OpCode.PushEcx, 1) && p.Emit(OpCode.MovEcxEbx, 2) && p.Emit(OpCode.AndEcx0F, 3) && p.Emit(OpCode.ShlEaxCl, 2) && p.Emit(OpCode.PopEcx, 1);
            case 2: return p.Emit(OpCode.AddEaxEbx, 2);
            case 3: return p.Emit(OpCode.NegEax, 2) && p.Emit(OpCode.AddEaxEbx, 2);
            case 4: return p.Emit(OpCode.ImulEaxEbx, 3);
            case 5: return p.Emit(OpCode.SubEaxEbx, 2);
            default: return true;
        }
    }

    public void ExecuteXCode(uint h, out uint r0, out uint r1)
    {
        uint seed = h & 0x7FU;
        h >>= 7;
        var prog = _programs[seed];
        r0 = prog.Execute(h);
        r1 = prog.Execute(~h);
    }

    public HxEntryDecryptor CreateDecryptor(ulong entryId, ulong entryKey)
    {
        ulong ek = entryKey;
        if ((entryId & 0x100000000UL) == 0) ek ^= FilterKey;
        ulong hdrSeed = ~ek;
        uint r0, r1;
        ExecuteXCode((uint)(ek & 0xFFFFFFFFUL), out r0, out r1);
        ulong fk0 = ((ulong)r0) | (((ulong)r1) << 32);
        ExecuteXCode((uint)((ek >> 32) & 0xFFFFFFFFUL), out r0, out r1);
        ulong fk1 = ((ulong)r0) | (((ulong)r1) << 32);
        long splitPos = (long)(((ulong)Offset + ((ek >> 16) & (ulong)Mask)) & 0xFFFFFFFFUL);
        byte[] headerKey = new byte[16];
        ExecuteXCode((uint)(hdrSeed & 0xFFFFFFFFUL), out r0, out r1);
        ulong v5 = ~(((ulong)r0) | (((ulong)r1) << 32));
        for (int i = 0, shift = 56; i < 8; i++, shift -= 8) headerKey[i] = (byte)((v5 >> shift) & 0xFFUL);
        ExecuteXCode((uint)(v5 & 0xFFFFFFFFUL), out r0, out r1);
        v5 = ~(((ulong)r0) | (((ulong)r1) << 32));
        for (int i = 0, shift = 56; i < 8; i++, shift -= 8) headerKey[8 + i] = (byte)((v5 >> shift) & 0xFFUL);
        return new HxEntryDecryptor(fk0, fk1, splitPos, headerKey);
    }
}

public sealed class HxEntryDecryptor
{
    private readonly byte _fdk0, _k0a, _k0b, _fdk1, _k1a, _k1b;
    private readonly long _p0a, _p0b, _p1a, _p1b, _splitPos;
    private readonly byte[] _headerKey;

    public HxEntryDecryptor(ulong fk0, ulong fk1, long splitPos, byte[] headerKey)
    {
        _splitPos = splitPos;
        _headerKey = headerKey;
        InitSpan(fk0, out _fdk0, out _k0a, out _k0b, out _p0a, out _p0b);
        InitSpan(fk1, out _fdk1, out _k1a, out _k1b, out _p1a, out _p1b);
    }

    private static void InitSpan(ulong fk, out byte fdk, out byte ka, out byte kb, out long pa, out long pb)
    {
        uint dk = (uint)((fk >> 8) & 0xFFFFUL);
        byte f = (byte)(fk & 0xFFUL);
        if (f == 0) f = 0xA5;
        fdk = f; ka = (byte)(dk & 0xFFU); kb = (byte)((dk >> 8) & 0xFFU);
        pa = (long)((fk >> 48) & 0xFFFFUL); pb = (long)((fk >> 32) & 0xFFFFUL);
        if (pa == pb) pb += 1;
    }

    public void DecryptInPlace(long virtualPos, byte[] buf, int offset, int count)
    {
        if (count <= 0) return;
        if (virtualPos < 16)
        {
            long endH = Math.Min(virtualPos + count, 16L);
            for (long p = virtualPos; p < endH; p++) buf[offset + (int)(p - virtualPos)] ^= _headerKey[(int)p];
        }
        long endPos = virtualPos + count;
        if (endPos <= _splitPos) DecryptSpan(virtualPos, buf, offset, count, _fdk0, _k0a, _k0b, _p0a, _p0b);
        else if (virtualPos >= _splitPos) DecryptSpan(virtualPos, buf, offset, count, _fdk1, _k1a, _k1b, _p1a, _p1b);
        else
        {
            int len0 = (int)(_splitPos - virtualPos);
            DecryptSpan(virtualPos, buf, offset, len0, _fdk0, _k0a, _k0b, _p0a, _p0b);
            DecryptSpan(_splitPos, buf, offset + len0, count - len0, _fdk1, _k1a, _k1b, _p1a, _p1b);
        }
    }

    private static void DecryptSpan(long startPos, byte[] buf, int offset, int count, byte fdk, byte ka, byte kb, long pa, long pb)
    {
        if (fdk != 0)
        {
            int end = offset + count;
            for (int i = offset; i < end; i++) buf[i] ^= fdk;
        }
        if (ka != 0 && pa >= startPos && pa < startPos + count) buf[offset + (int)(pa - startPos)] ^= ka;
        if (kb != 0 && pb >= startPos && pb < startPos + count) buf[offset + (int)(pb - startPos)] ^= kb;
    }
}

public static class ExtractSelected
{
    private static uint ComputeAdler32(byte[] data, int len)
    {
        const uint MOD = 65521U;
        uint a = 1U, b = 0U;
        int i = 0;
        while (i < len)
        {
            int chunk = Math.Min(5552, len - i);
            for (int j = 0; j < chunk; j++) { a += data[i++]; b += a; }
            a %= MOD; b %= MOD;
        }
        return (b << 16) | a;
    }

    private static void ReadExact(Stream s, byte[] buf, int offset, int count)
    {
        int total = 0;
        while (total < count)
        {
            int r = s.Read(buf, offset + total, count - total);
            if (r <= 0) throw new EndOfStreamException("Unexpected EOF");
            total += r;
        }
    }

    private static byte[] DecompressZlibFull(byte[] packed)
    {
        if (packed.Length < 6) return new byte[0];
        using (var ms = new MemoryStream(packed, 2, packed.Length - 6))
        using (var ds = new DeflateStream(ms, CompressionMode.Decompress))
        using (var outMs = new MemoryStream())
        {
            ds.CopyTo(outMs);
            return outMs.ToArray();
        }
    }

    private static byte[] ReadEntryFull(FileStream fs, ArrayList segments, long expectedOrig, HxEntryDecryptor dec)
    {
        byte[] output = new byte[expectedOrig];
        int outPos = 0;
        foreach (ArrayList seg in segments)
        {
            int segFlags = Convert.ToInt32(seg[0]);
            long segOffset = Convert.ToInt64(seg[1]);
            int origSize = Convert.ToInt32(seg[2]);
            int packedSize = Convert.ToInt32(seg[3]);
            byte[] packed = new byte[packedSize];
            fs.Position = segOffset;
            ReadExact(fs, packed, 0, packedSize);
            byte[] plainSeg = ((segFlags & 7) == 1) ? DecompressZlibFull(packed) : packed;
            if (plainSeg.Length != origSize) throw new InvalidDataException("Segment decompressed size mismatch");
            if (dec != null) dec.DecryptInPlace(outPos, plainSeg, 0, origSize);
            Buffer.BlockCopy(plainSeg, 0, output, outPos, origSize);
            outPos += origSize;
        }
        return output;
    }

    public static int Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.Error.WriteLine("Usage: ExtractSelected <gameDir> <reportsPhase0Dir> <planJsonPath>");
            return 1;
        }
        string gameDir = args[0];
        string reportsDir = args[1];
        string planPath = args[2];

        var json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue, RecursionLimit = 256 };
        var scheme = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(reportsDir, "ginka_hxv4_scheme.json"), Encoding.UTF8));
        var engine = new HxCipherEngine(
            Convert.ToUInt32(scheme["mask"]),
            Convert.ToUInt32(scheme["offset"]),
            ulong.Parse((string)scheme["filterKey"], CultureInfo.InvariantCulture),
            Convert.ToInt32(scheme["randomType"]),
            ((ArrayList)scheme["prologOrder"]).Cast<object>().Select(Convert.ToByte).ToArray(),
            ((ArrayList)scheme["oddBranchOrder"]).Cast<object>().Select(Convert.ToByte).ToArray(),
            ((ArrayList)scheme["evenBranchOrder"]).Cast<object>().Select(Convert.ToByte).ToArray(),
            ((ArrayList)scheme["controlBlockInvU32"]).Cast<object>().Select(Convert.ToUInt32).ToArray()
        );
        var hxv4Tables = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(reportsDir, "hxv4_decrypted_tables.json"), Encoding.UTF8));
        var plan = json.Deserialize<ArrayList>(File.ReadAllText(planPath, Encoding.UTF8));

        var byArc = new Dictionary<string, List<Dictionary<string, object>>>();
        foreach (Dictionary<string, object> item in plan)
        {
            string arc = (string)item["archive"];
            if (!arc.EndsWith(".xp3", StringComparison.OrdinalIgnoreCase)) arc += ".xp3";
            List<Dictionary<string, object>> list;
            if (!byArc.TryGetValue(arc, out list)) byArc[arc] = list = new List<Dictionary<string, object>>();
            list.Add(item);
        }

        int extracted = 0, skipped = 0, adlerOk = 0, adlerFail = 0;
        foreach (var kv in byArc)
        {
            string arcName = kv.Key;
            var rawEntries = json.Deserialize<ArrayList>(File.ReadAllText(Path.Combine(reportsDir, arcName + ".raw_entries.json"), Encoding.UTF8));
            var hxList = (ArrayList)hxv4Tables[arcName];
            var hxByUname = new Dictionary<string, Dictionary<string, object>>(hxList.Count);
            foreach (Dictionary<string, object> hx in hxList) hxByUname[(string)hx["unicode_name"]] = hx;

            string xp3Path = Path.Combine(gameDir, arcName);
            using (var fs = new FileStream(xp3Path, FileMode.Open, FileAccess.Read, FileShare.Read, 65536))
            {
                foreach (var item in kv.Value)
                {
                    int idx = Convert.ToInt32(item["index"]);
                    string outPath = (string)item["output"];
                    var re = (Dictionary<string, object>)rawEntries[idx];
                    long origSize = Convert.ToInt64(re["original"]);
                    if (File.Exists(outPath) && new FileInfo(outPath).Length == origSize)
                    {
                        skipped++;
                        continue;
                    }
                    string uname = (string)re["name"];
                    uint expectedAdler = Convert.ToUInt32(re["adler"]);
                    uint entryFlags = Convert.ToUInt32(re["flags"]);
                    var segs = (ArrayList)re["segments"];
                    Dictionary<string, object> hxItem;
                    HxEntryDecryptor dec = null;
                    if (hxByUname.TryGetValue(uname, out hxItem) && entryFlags != 0)
                    {
                        ulong eid = ulong.Parse(Convert.ToString(hxItem["id"], CultureInfo.InvariantCulture), CultureInfo.InvariantCulture);
                        ulong ekey = ulong.Parse(Convert.ToString(hxItem["key"], CultureInfo.InvariantCulture), CultureInfo.InvariantCulture);
                        dec = engine.CreateDecryptor(eid, ekey);
                    }
                    byte[] full = ReadEntryFull(fs, segs, origSize, dec);
                    if (ComputeAdler32(full, full.Length) == expectedAdler) adlerOk++;
                    else { adlerFail++; Console.Error.WriteLine("ADLER_FAIL " + arcName + "#" + idx); }
                    Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                    File.WriteAllBytes(outPath, full);
                    extracted++;
                }
            }
        }
        Console.WriteLine(json.Serialize(new Dictionary<string, object> {
            {"extracted", extracted}, {"skipped", skipped}, {"adlerOk", adlerOk}, {"adlerFail", adlerFail}
        }));
        return adlerFail > 0 ? 2 : 0;
    }
}
