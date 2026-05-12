import 'package:flutter/material.dart';

class PersonaChip extends StatelessWidget {
  const PersonaChip({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🏛️ ', style: TextStyle(fontSize: 16)),
          Text(
            '歷史大叔',
            style: TextStyle(color: Color(0xFF4A9EFF), fontSize: 16),
          ),
        ],
      ),
    );
  }
}
