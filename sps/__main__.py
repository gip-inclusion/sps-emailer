import argparse, sys

def main(argv=None):
    parser = argparse.ArgumentParser(prog="sps", description="Pipeline e-mails SPS")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("convert", help="MD historique → JSON anonyme (1/conseiller)")
    p.add_argument("md"); p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("deanon", help="JSON anonyme + CSV réel → JSON nominatif")
    p.add_argument("indir"); p.add_argument("--csv", required=True)
    p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("render", help="JSON → HTML (1/conseiller)")
    p.add_argument("indir"); p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("send", help="Envoi via Brevo")
    p.add_argument("indir"); p.add_argument("--test", action="store_true")
    p.add_argument("--via", help="Proxy egress (ex. socks5h://127.0.0.1:1080), sinon BREVO_PROXY")

    p = sub.add_parser("schedule", help="Envoi programmé via Brevo (scheduledAt)")
    p.add_argument("indir"); p.add_argument("--at", required=True)
    p.add_argument("--test", action="store_true")
    p.add_argument("--via", help="Proxy egress (ex. socks5h://127.0.0.1:1080), sinon BREVO_PROXY")

    p = sub.add_parser("cancel", help="Annule un envoi programmé Brevo (par runId, ou messageId)")
    p.add_argument("run_id")
    p.add_argument("--via", help="Proxy egress (ex. socks5h://127.0.0.1:1080), sinon BREVO_PROXY")

    p = sub.add_parser("purge", help="Efface les sorties nominatives anciennes (hygiène vie privée)")
    p.add_argument("dirs", nargs="*", help="dossiers à purger (défaut : out/json-nom out/html)")
    p.add_argument("--older-than", type=int, default=7, metavar="JOURS",
                   help="seuil d'âge en jours (défaut 7)")
    p.add_argument("-y", "--yes", action="store_true", help="ne pas demander confirmation")

    args = parser.parse_args(argv)

    if args.cmd == "convert":
        from sps.convert import run_convert
        run_convert(args.md, args.out)
    elif args.cmd == "deanon":
        from sps.deanon import run_deanon
        run_deanon(args.indir, args.csv, args.out)
    elif args.cmd == "render":
        from sps.render import run_render
        run_render(args.indir, args.out)
    elif args.cmd in ("send", "schedule"):
        from sps.brevo import run_send
        run_send(args.indir, test=args.test,
                 scheduled_at=getattr(args, "at", None),
                 proxy=getattr(args, "via", None))
    elif args.cmd == "cancel":
        from sps.brevo import run_cancel
        run_cancel(args.run_id, proxy=getattr(args, "via", None))
    elif args.cmd == "purge":
        from sps.purge import run_purge
        run_purge(args.dirs or None, older_than_days=args.older_than, assume_yes=args.yes)

if __name__ == "__main__":
    sys.exit(main())
