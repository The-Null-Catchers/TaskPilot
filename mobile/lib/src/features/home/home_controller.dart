import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api.dart';

class Workspace {
  const Workspace({required this.id, required this.name});
  final String id;
  final String name;
  factory Workspace.fromJson(Map<String, dynamic> json) => Workspace(id: json['id'] as String, name: json['name'] as String);
  Map<String, dynamic> toJson() => {'id': id, 'name': name};
}

class HomeState {
  const HomeState({this.loading = true, this.offline = false, this.workspaces = const [], this.error});
  final bool loading;
  final bool offline;
  final List<Workspace> workspaces;
  final String? error;
}

final homeProvider = StateNotifierProvider<HomeController, HomeState>((ref) => HomeController(ref.watch(apiProvider))..load());

class HomeController extends StateNotifier<HomeState> {
  HomeController(this.api) : super(const HomeState());
  final ApiClient api;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await api.dio.get('/api/v1/workspaces');
      final items = (response.data as List).cast<Map<String, dynamic>>().map(Workspace.fromJson).toList();
      await prefs.setString('cached_workspaces', jsonEncode(items.map((e) => e.toJson()).toList()));
      state = HomeState(loading: false, workspaces: items);
    } catch (_) {
      final cached = prefs.getString('cached_workspaces');
      if (cached != null) {
        final items = (jsonDecode(cached) as List).cast<Map<String, dynamic>>().map(Workspace.fromJson).toList();
        state = HomeState(loading: false, offline: true, workspaces: items);
      } else {
        state = const HomeState(loading: false, offline: true, error: 'Connect to the internet to load your workspace.');
      }
    }
  }
}
