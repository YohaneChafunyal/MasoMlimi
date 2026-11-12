
import 'package:flutter/material.dart';

class C {
  static const green = Color(0xFF22C55E);
  static const greenDark = Color(0xFF15803D);
  static const greenSoft = Color(0xFFDCFCE7);
  static const greenGradTop = Color(0xFFBBF7D0);
  static const greenGradBot = Color(0xFF4ADE80);
  static const bg = Color(0xFFF3F4F6);
  static const card = Colors.white;
  static const text = Color(0xFF111827);
  static const muted = Color(0xFF6B7280);
  static const border = Color(0xFFE5E7EB);
  static const amber = Color(0xFFF59E0B);
  static const amberSoft = Color(0xFFFFFBEB);
  static const red = Color(0xFFEF4444);
  static const redSoft = Color(0xFFFEE2E2);
  static const blueSoft = Color(0xFFEFF6FF);
}

ThemeData masoTheme() {
  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: C.bg,
    colorScheme: ColorScheme.fromSeed(seedColor: C.green, primary: C.greenDark),
    appBarTheme: const AppBarTheme(
      backgroundColor: C.card,
      foregroundColor: C.text,
      elevation: 0,
      titleTextStyle: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: C.text),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: C.greenDark,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: C.card,
      indicatorColor: C.greenSoft,
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith((s) {
        final sel = s.contains(WidgetState.selected);
        return TextStyle(fontSize: 11, fontWeight: sel ? FontWeight.w700 : FontWeight.w500, color: sel ? C.greenDark : C.muted);
      }),
    ),
  );
}

class DashCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final Gradient? gradient;
  final Color? color;
  const DashCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.gradient, this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        gradient: gradient,
        color: gradient == null ? (color ?? C.card) : null,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 18, offset: const Offset(0, 8))],
      ),
      child: child,
    );
  }
}

class StatMini extends StatelessWidget {
  final String value;
  final String label;
  final IconData icon;
  final Color tint;
  const StatMini({super.key, required this.value, required this.label, required this.icon, required this.tint});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: C.card, borderRadius: BorderRadius.circular(20), boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 4)),
        ]),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36, height: 36,
              decoration: BoxDecoration(color: tint.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: tint, size: 20),
            ),
            const SizedBox(height: 12),
            Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: C.text)),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

class CategoryTile extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color bg;
  final Color iconColor;
  final VoidCallback onTap;
  final String? imageAsset;
  const CategoryTile({
    super.key,
    required this.label,
    required this.icon,
    required this.bg,
    required this.iconColor,
    required this.onTap,
    this.imageAsset,
  });
  @override
  Widget build(BuildContext context) {
    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: SizedBox(
                  width: 64,
                  height: 64,
                  child: imageAsset != null
                      ? Image.asset(
                          imageAsset!,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Container(
                            color: Colors.white.withValues(alpha: 0.9),
                            child: Icon(icon, color: iconColor, size: 32),
                          ),
                        )
                      : Container(
                          color: Colors.white.withValues(alpha: 0.9),
                          child: Icon(icon, color: iconColor, size: 32),
                        ),
                ),
              ),
              const SizedBox(height: 10),
              Text(label, textAlign: TextAlign.center, maxLines: 2, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}

class SoftListCard extends StatelessWidget {
  final Widget leading;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Color? leadingBg;
  final VoidCallback? onTap;
  const SoftListCard({super.key, required this.leading, required this.title, this.subtitle, this.trailing, this.leadingBg, this.onTap});
  @override
  Widget build(BuildContext context) {
    return Material(
      color: C.card,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 14, offset: const Offset(0, 6))],
          ),
          child: Row(
            children: [
              Container(
                width: 52, height: 52,
                decoration: BoxDecoration(color: leadingBg ?? C.greenSoft, borderRadius: BorderRadius.circular(16)),
                child: Center(child: leading),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
                    if (subtitle != null) Text(subtitle!, style: const TextStyle(fontSize: 12.5, color: C.muted)),
                  ],
                ),
              ),
              trailing ?? const Icon(Icons.chevron_right, color: C.muted),
            ],
          ),
        ),
      ),
    );
  }
}
