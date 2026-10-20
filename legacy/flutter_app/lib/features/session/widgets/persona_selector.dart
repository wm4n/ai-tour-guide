import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class PersonaSelector extends ConsumerWidget {
  const PersonaSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedId = ref.watch(sessionProvider).persona;

    return Column(
      children: kPersonas.map((persona) {
        final isSelected = persona.id == selectedId;
        return GestureDetector(
          onTap: () => ref.read(sessionProvider.notifier).setPersona(persona.id),
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 6),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF0F3460),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected
                    ? const Color(0xFF4A9EFF)
                    : Colors.transparent,
                width: 2,
              ),
            ),
            child: Row(
              children: [
                Text(persona.emoji, style: const TextStyle(fontSize: 24)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        persona.displayName,
                        style: TextStyle(
                          color: isSelected
                              ? const Color(0xFF4A9EFF)
                              : Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        persona.description,
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                if (isSelected)
                  const Icon(Icons.check_circle, color: Color(0xFF4A9EFF)),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}
